from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

# Import models and schemas (to be created)
# from .models import models
# from .schemas import schemas
# from .database import get_db

app = FastAPI(
    title="Smart Village Management API",
    description="API for Smart Village Management System",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to Smart Village Management API", "version": "0.1.0"}

# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Include routers from different modules
# app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
# app.include_router(users_router, prefix="/users", tags=["Users"])
# app.include_router(properties_router, prefix="/properties", tags=["Properties"])
# app.include_router(invoices_router, prefix="/invoices", tags=["Invoices"])
# app.include_router(payments_router, prefix="/payments", tags=["Payments"])
# app.include_router(access_router, prefix="/access", tags=["Access Control"])

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return {"detail": exc.detail, "status_code": exc.status_code}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
