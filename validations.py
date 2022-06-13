"""Validations of the collections"""
import re


def validate_user_creation(values):
    print("entered user validation")
    user_regex = {
        'username': '^[a-zA-Z0-9\-]{4,12}$', #username regex
        'email': '^([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+$', # email regex
        'name': '^[a-zA-Z]{1,}$', # name regex
        'last_name': '^[a-zA-Z]{1,}$',
        'password': '^[a-zA-Z0-9]{8,}$' # password can be anything... but it has to be something
    }
    for key in user_regex:
        if key not in values:
            return False

    for key, value in values.items():
        print(f'checking key {key}')
        if key != 'avatar':
            if key not in user_regex.keys():        
                    print(f'{key} is not in user_regex')
                    return False
            if not re.match(user_regex[key], value):
                    print(f'{value} didnt mmatch {user_regex[key]}')
                    return False
    return True


def validate_group_creation(values):
    print("entered group validation")
    group_regex = {
        'username': '^[a-zA-Z0-9\-]{4,12}$', #username regex
        'email': '^([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+$', # email regex
        'name': '^[a-zA-Z]{1,}$', # name regex
        'last_name': '^[a-zA-Z]{1,}$',
        'password': '^[a-zA-Z0-9]{8,}$' # password can be anything... but it has to be something
    }
    
    return 1