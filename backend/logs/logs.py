import logging


def log_middleware(func):
    async def wrapper(*args, **kwargs):
        logging.info(f'Started {func.__name__} c args={args} kwargs={kwargs}')

        try:
            response = await func(*args, **kwargs)
            return response
        except Exception as e:
            logging.error(f'Exception caught in {func.__name__}: {e}')
        finally:
            logging.info(f'Ended {func.__name__}')

    return wrapper
