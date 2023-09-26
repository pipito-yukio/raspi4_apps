import os

from plot_weather import app, app_logger

"""
This module load after app(==__init__.py)
"""

if __name__ == "__main__":
    has_prod = os.environ.get("FLASK_ENV") == "production"
    # app config SERVER_NAME
    srv_host = app.config["SERVER_NAME"]
    srv_hosts = srv_host.split(":")
    host, port = srv_hosts[0], srv_hosts[1]
    app_logger.info("run.py in host: {}, port: {}".format(host, port))
    if has_prod:
        # Production mode
        try:
            # Prerequisites: pip install waitress
            from waitress import serve

            app_logger.info("Production start.")
            # console log for Reqeust suppress: _quiet=True  
            serve(app, host=host, port=port, _quiet=True)
        except ImportError:
            # Production with flask,debug False
            app_logger.info("Development start, without debug.")
            app.run(host=host, port=port, debug=False)
    else:
        # Development mode
        app_logger.info("Development start, with debug.")
        app.run(host=host, port=port, debug=True)
