import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta
from starlette.responses import RedirectResponse

from config import settings
from database import get_db, engine
from models import Base, User, AudioFile
from auth import get_current_active_user, create_access_token
from oauth import oauth, get_yandex_user_info

app = FastAPI(
    title="Audio File Service",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Создаем директорию для хранения файлов
os.makedirs(settings.AUDIO_FILES_DIR, exist_ok=True)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def root():
    return {"message": "Welcome to Audio File Service"}

@app.get("/auth/yandex")
async def yandex_auth_start() -> RedirectResponse:
    async with oauth:
        url = await oauth.get_authorization_url()
        return RedirectResponse(url=url)

@app.get("/auth/yandex/callback")
async def yandex_auth_callback(
    user_info = Depends(get_yandex_user_info),
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            select(User).where(User.yandex_id == str(user_info.id))
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                yandex_id=str(user_info.id),
                email=user_info.email,
                username=user_info.display_name or "",
                is_superuser=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@app.get("/users/me", response_model=dict)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser
    }

@app.get("/users/{user_id}", response_model=dict)
async def read_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser
    }

@app.patch("/users/me", response_model=dict)
async def update_user(
    username: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    current_user.username = username
    await db.commit()
    await db.refresh(current_user)
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser
    }

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    await db.delete(user)
    await db.commit()
    return {"message": "User deleted successfully"}

@app.post("/audio/upload", response_model=dict)
async def upload_audio(
    file: UploadFile,
    filename: str = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    if not file.filename.lower().endswith(('.mp3', '.wav', '.ogg')):
        raise HTTPException(
            status_code=400,
            detail="Only .mp3, .wav, and .ogg files are allowed"
        )
    
    if not filename:
        filename = file.filename
    
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{filename}{file_extension}"
    file_path = os.path.join(settings.AUDIO_FILES_DIR, unique_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        )
    
    audio_file = AudioFile(
        filename=filename,
        file_path=file_path,
        owner_id=current_user.id
    )
    db.add(audio_file)
    await db.commit()
    await db.refresh(audio_file)
    
    return {
        "id": audio_file.id,
        "filename": audio_file.filename,
        "file_path": audio_file.file_path,
        "created_at": audio_file.created_at,
        "owner_id": audio_file.owner_id
    }

@app.get("/audio/files", response_model=list[dict])
async def get_audio_files(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AudioFile).where(AudioFile.owner_id == current_user.id)
    )
    audio_files = result.scalars().all()
    
    return [
        {
            "id": file.id,
            "filename": file.filename,
            "file_path": file.file_path,
            "created_at": file.created_at
        }
        for file in audio_files
    ]

@app.post("/token/refresh")
async def refresh_token(
    current_user: User = Depends(get_current_active_user)
):
    try:
        access_token = create_access_token(
            data={"sub": str(current_user.id)},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 