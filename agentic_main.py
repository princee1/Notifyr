from app.utils.globals import APP_MODE,CAPABILITIES

if CAPABILITIES['agentic']:
    from app.container import Get, build_container
    from app.utils.prettyprint import PrettyPrinter_
    build_container()

    from app.server.agentic_server import bootstrap_agent_app
    app = bootstrap_agent_app()
    PrettyPrinter_.show(1, print_stack=False)
    PrettyPrinter_.space_line()

    
    if __name__ == "__main__":
        
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        ...

else:
    ...


