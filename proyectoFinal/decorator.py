from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def usuario_no_admin_requerido(view_func):
    @wraps(view_func)
    def accesoNoAdmin(request, *args, **kwargs):
        if request.user.is_superuser:
            messages.error(request, "No tienes permiso para acceder a esta página.")
            return redirect(
                'inicio')
        return view_func(request, *args, **kwargs)

    return accesoNoAdmin
