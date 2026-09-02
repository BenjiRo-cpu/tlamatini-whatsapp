from tlamatini.app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(host=app.config["TLAMATINI_CONFIG"].host,
            port=app.config["TLAMATINI_CONFIG"].port,
            debug=False)
