import os
import logging
import asyncio
import pandas as pd
import requests
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import aiofiles
import tempfile
import re

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CSV Contact Manager Agent")

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MAILCHIMP_API_KEY = os.getenv("MAILCHIMP_API_KEY")
MAILCHIMP_LIST_ID = os.getenv("MAILCHIMP_LIST_ID")
MAILCHIMP_SERVER_PREFIX = os.getenv("MAILCHIMP_SERVER_PREFIX")
PIPEDRIVE_API_KEY = os.getenv("PIPEDRIVE_API_KEY")
PIPEDRIVE_DOMAIN = os.getenv("PIPEDRIVE_DOMAIN")

# Data models
class Contact(BaseModel):
    name: str
    email: str
    linkedin_url: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class ContactReview(BaseModel):
    session_id: str
    contact_index: int
    add_to_mailchimp: bool
    add_to_pipedrive: bool

# In-memory storage for active reviews (in production, use Redis/database)
active_reviews: Dict[str, List[Contact]] = {}

@app.get("/")
async def root():
    return {"message": "CSV Contact Manager Agent is running!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def validate_email(email: str) -> bool:
    """Basic email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_linkedin_url(url: str) -> bool:
    """Basic LinkedIn URL validation"""
    if not url or pd.isna(url):
        return False
    url = str(url).strip()
    return 'linkedin.com' in url.lower()

def clean_linkedin_url(url: str) -> str:
    """Clean and standardize LinkedIn URL"""
    if not url or pd.isna(url):
        return ""
    
    url = str(url).strip()
    
    # Remove tracking parameters
    if '?' in url:
        url = url.split('?')[0]
    
    # Ensure it starts with https://
    if not url.startswith('http'):
        url = 'https://' + url
    
    return url

def parse_csv(file_path: str) -> List[Contact]:
    """Parse CSV file and extract contacts"""
    try:
        df = pd.read_csv(file_path)
        contacts = []
        
        for _, row in df.iterrows():
            # Extract required fields
            name = str(row.get('name', '')).strip()
            email = str(row.get('email', '')).strip()
            linkedin_url = clean_linkedin_url(row.get('What is your LinkedIn profile?', ''))
            
            # Skip if missing essential data
            if not name or not email or not linkedin_url:
                continue
            
            # Validate email
            if not validate_email(email):
                continue
            
            # Validate LinkedIn URL
            if not validate_linkedin_url(linkedin_url):
                continue
            
            # Extract first and last name
            first_name = str(row.get('first_name', '')).strip() if pd.notna(row.get('first_name')) else ""
            last_name = str(row.get('last_name', '')).strip() if pd.notna(row.get('last_name')) else ""
            
            contact = Contact(
                name=name,
                email=email,
                linkedin_url=linkedin_url,
                first_name=first_name if first_name else None,
                last_name=last_name if last_name else None
            )
            contacts.append(contact)
        
        return contacts
    
    except Exception as e:
        logger.error(f"Error parsing CSV: {e}")
        raise HTTPException(status_code=400, detail=f"Error parsing CSV: {str(e)}")

async def add_to_mailchimp(contact: Contact) -> bool:
    """Add contact to Mailchimp"""
    if not all([MAILCHIMP_API_KEY, MAILCHIMP_LIST_ID, MAILCHIMP_SERVER_PREFIX]):
        logger.warning("Mailchimp credentials not configured")
        return False
    
    try:
        url = f"https://{MAILCHIMP_SERVER_PREFIX}.api.mailchimp.com/3.0/lists/{MAILCHIMP_LIST_ID}/members"
        
        data = {
            "email_address": contact.email,
            "status": "subscribed",
            "merge_fields": {
                "FNAME": contact.first_name or contact.name.split()[0],
                "LNAME": contact.last_name or " ".join(contact.name.split()[1:]) if len(contact.name.split()) > 1 else "",
                "LINKEDIN": contact.linkedin_url
            }
        }
        
        headers = {
            "Authorization": f"Bearer {MAILCHIMP_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code in [200, 201]:
            logger.info(f"Successfully added {contact.email} to Mailchimp")
            return True
        else:
            logger.error(f"Failed to add {contact.email} to Mailchimp: {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error adding to Mailchimp: {e}")
        return False

async def add_to_pipedrive(contact: Contact) -> bool:
    """Add contact to Pipedrive"""
    if not all([PIPEDRIVE_API_KEY, PIPEDRIVE_DOMAIN]):
        logger.warning("Pipedrive credentials not configured")
        return False
    
    try:
        # First, create a person
        person_url = f"https://{PIPEDRIVE_DOMAIN}.pipedrive.com/api/v1/persons"
        
        person_data = {
            "name": contact.name,
            "email": [{"value": contact.email, "primary": True, "label": "work"}],
            "linkedin": contact.linkedin_url
        }
        
        headers = {"Content-Type": "application/json"}
        params = {"api_token": PIPEDRIVE_API_KEY}
        
        response = requests.post(person_url, json=person_data, headers=headers, params=params)
        
        if response.status_code == 201:
            person_id = response.json()["data"]["id"]
            logger.info(f"Successfully added {contact.email} to Pipedrive as person ID {person_id}")
            return True
        else:
            logger.error(f"Failed to add {contact.email} to Pipedrive: {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error adding to Pipedrive: {e}")
        return False

@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Upload and parse CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        # Parse CSV
        contacts = parse_csv(temp_file_path)
        
        # Clean up temp file
        os.unlink(temp_file_path)
        
        if not contacts:
            raise HTTPException(status_code=400, detail="No valid contacts found in CSV")
        
        # Generate review session ID
        import uuid
        session_id = str(uuid.uuid4())
        active_reviews[session_id] = contacts
        
        return {
            "session_id": session_id,
            "total_contacts": len(contacts),
            "contacts": [contact.dict() for contact in contacts[:5]]  # Show first 5 as preview
        }
    
    except Exception as e:
        logger.error(f"Error processing CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/review-contact")
async def review_contact(review: ContactReview):
    """Review and process a single contact"""
    session_id = review.session_id
    
    if not session_id or session_id not in active_reviews:
        raise HTTPException(status_code=404, detail="Review session not found")
    
    contacts = active_reviews[session_id]
    
    if review.contact_index >= len(contacts):
        raise HTTPException(status_code=400, detail="Invalid contact index")
    
    contact = contacts[review.contact_index]
    results = {}
    
    # Add to Mailchimp if requested
    if review.add_to_mailchimp:
        results["mailchimp"] = await add_to_mailchimp(contact)
    
    # Add to Pipedrive if requested
    if review.add_to_pipedrive:
        results["pipedrive"] = await add_to_pipedrive(contact)
    
    return {
        "contact": contact.dict(),
        "results": results,
        "processed": True
    }

@app.get("/contacts/{session_id}")
async def get_contacts(session_id: str):
    """Get all contacts for a review session"""
    if session_id not in active_reviews:
        raise HTTPException(status_code=404, detail="Review session not found")
    
    contacts = active_reviews[session_id]
    return {
        "session_id": session_id,
        "total_contacts": len(contacts),
        "contacts": [contact.dict() for contact in contacts]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 