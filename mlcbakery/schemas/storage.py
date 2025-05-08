from pydantic import BaseModel
from typing import Optional, Dict, Any

class DataUploadResponse(BaseModel):
    """Response model for data upload endpoint"""
    success: bool
    file_path: str
    collection_name: str
    dataset_name: str
    file_number: int

class DataDownloadResponse(BaseModel):
    """Response model for data download info endpoint"""
    download_url: str
    file_path: str
    collection_name: str
    dataset_name: str
    file_number: int