from app.utils.globals import APP_MODE,CAPABILITIES

if CAPABILITIES['agent']:
    from app.container import Get, build_container
    build_container()

    from app.agentic import bootstrap_agent_app
    app = bootstrap_agent_app()

else:
    ...


