from app.utils.globals import APP_MODE,CAPABILITIES

if CAPABILITIES['agentic']:
    from app.container import Get, build_container
    build_container()

    from app.agentic import bootstrap_agent_app
    app = bootstrap_agent_app()
    
    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        ...

else:
    ...


