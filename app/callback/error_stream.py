from app.classes.profiles import ProfileErrorProtocol
from app.utils.constant import StreamConstant,SubConstant
from app.models.profile_model import ErrorProfileModel
from app.container import Get
from app.services import MongooseService,RedisService,ProfileService
from app.definition._service import MiniStateProtocol

async def ProfileErrorStream(entries:list[tuple[str,ProfileErrorProtocol]]):
    mongooseService:MongooseService = Get(MongooseService)
    redisService:RedisService = Get(RedisService)
    profileService:ProfileService = Get(ProfileService)

    data=set()
    ids_list = []
    service_ids:dict[str,list] = {}
    

    async with mongooseService.statusLock.reader:
        
        for id,message in entries:
            error= {
                'profile_id':message.get('profile_id'),
                'error_code' : message.get('error_code',-1),
                'error_name' : message.get('error_name',None),
                'error_description' : message.get('error_description',None),
                'error_type' : message.get('error_type','general'),
                'error_level' : message.get('error_level','message'),

            }
            service_status= message['profile_status']

            data.add(frozenset(error.items()))
            ids_list.append(id)

            profile_id = error['profile_id']
            if profile_id not in service_ids:
                service_ids[profile_id] = []

            service_ids[profile_id].append(service_status)

        try:
            await ErrorProfileModel.insert_many([ErrorProfileModel(**dict(e)) for e in data])

            async with profileService.statusLock.reader:
                for sid,status in service_ids.items():
                                    
                    if sid not in profileService.MiniServiceStore:
                        continue
                    
                    miniService = profileService.MiniServiceStore.get(sid)

                    async with miniService.statusLock.reader:
                        status = max(status)
                        if status == miniService.service_status.value:
                            continue
                        await redisService.publish_data(SubConstant.MINI_SERVICE_STATUS,
                        MiniStateProtocol(
                            id=sid,
                            service=ProfileService,
                            status=status,
                            to_build=False,
                            to_destroy=True,
                            recursive=True,
                        ))    
        except:
            ...
        
        return ids_list




Profile_Error_Stream={

    StreamConstant.PROFILE_ERROR_STREAM: ProfileErrorStream
}
