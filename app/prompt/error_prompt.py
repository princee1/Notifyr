def ERROR_TEMPLATE(content:str|dict,retry:bool=False,instruction:str=None)->str:
    return f'<error> <content>{content}</content> </error>'