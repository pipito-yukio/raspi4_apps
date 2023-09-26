import os

base_dir = os.path.abspath(os.path.dirname(__file__))

# Define the database
# Application threads.
#THREADS_PER_PAGE = 2


class BaseConfig(object):
    DEUBG = True


class DevConfig(BaseConfig):
    pass


class ProdConfig(BaseConfig):
    DEBUG = False


config_dict = {'development': DevConfig, 'production': ProdConfig, }