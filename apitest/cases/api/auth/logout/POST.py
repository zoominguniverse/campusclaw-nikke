from scenarios import auth_logout

ORDER = 91
OPERATION_ID = 'auth_logout'

def run(context):
    auth_logout(context)
