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
from .routes import auth, users, properties, invoices, payments, access, expenses, visitors, qr_access, hardware_simulation, gate_schedule, notifications

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(properties.router, prefix="/properties", tags=["Properties"])
app.include_router(invoices.router, prefix="/invoices", tags=["Invoices"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(access.router, prefix="/access", tags=["Access Control"])
app.include_router(expenses.router, prefix="/expenses", tags=["Expenses"])
app.include_router(visitors.router, prefix="/visitors", tags=["Visitor Management"])
app.include_router(qr_access.router, prefix="/qr", tags=["QR Code Access"])
app.include_router(hardware_simulation.router, prefix="/hardware", tags=["Hardware Simulation"])
app.include_router(gate_schedule.router, prefix="/gate-schedules", tags=["Gate Scheduling"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return {"detail": exc.detail, "status_code": exc.status_code}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
