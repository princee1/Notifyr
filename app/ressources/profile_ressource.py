from typing import Type
from fastapi import Request
from app.definition._ressource import BaseHTTPRessource, HTTPRessource
from app.models.profile_model import ProfilModelValues, ProfileModel, ProfileModelTypeDoesNotExistsError
from app.services.profile_service import ProfileService

PROFILE_PREFIX = 'profile'

async def pipe_profil_model(profile_type:str,request:Request):
    body = await request.json()  # <- untyped dict
    
    if profile_type not in ProfilModelValues.keys():
        raise ProfileModelTypeDoesNotExistsError(profile_type)
    
    profile_type:Type[ProfileModel] = ProfilModelValues[profile_type]
    return profile_type.model_validate(body)
    



@HTTPRessource(PROFILE_PREFIX)
class ProfileRessource(BaseHTTPRessource):
    
    def __init__(self,profileService:ProfileService,):
        super().__init__()
        self.profileService = profileService

    
    def create_profile():
        ...