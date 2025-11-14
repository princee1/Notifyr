from typing import ClassVar, Optional
from app.classes.profiles import BaseProfileModel
from app.utils.constant import MongooseDBConstant

######################################################
# Communication-related Profiles (Root)
######################################################

class WebhookProfileModel(BaseProfileModel):

    _collection:ClassVar[Optional[str]]= MongooseDBConstant.WEBHOOK_PROFILE_COLLECTION
    class Settings:
        abstract=True
        is_root=True
        collection=MongooseDBConstant.WEBHOOK_PROFILE_COLLECTION

