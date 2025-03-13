def user_info(request):
    if request.user.is_authenticated:
        return {
            'admin': request.user.is_staff,
            'nombre': request.user.username
        }
    return {
        'admin': None,
        'nombre': None
    }