from django.contrib.auth.models import User

# Create your models here.

from django.db import models


class Rutas(models.Model):
    titulo = models.CharField(max_length=45)
    fecha = models.DateField()
    tiempo = models.TimeField()
    distancia = models.DecimalField(max_digits=5, decimal_places=2)
    velocidad = models.DecimalField(max_digits=5, decimal_places=2)
    ascenso = models.IntegerField()
    descenso = models.IntegerField()
    dureza = models.CharField(max_length=45)
    imagen = models.ImageField(upload_to="proyectoFinal", null=True, blank=True)
    publico = models.BooleanField(default=False)
    fechaSubida = models.DateTimeField(auto_now_add=True)
    # imagen = models.CharField(max_length=100, blank=True, null=True)
    idUsuario = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.titulo} - {self.idUsuario.first_name}"


class Comentarios(models.Model):
    comentario = models.CharField(max_length=300)
    id_ruta = models.ForeignKey(Rutas, on_delete=models.CASCADE, related_name="comentarios")


#
# class tiposBicicletas(models.Model):
#     nombre_tipo = models.CharField(max_length=50, unique=True)
#     tipoNeumatico = models.CharField(max_length=45)


class caracteristicas(models.Model):
    edad = models.PositiveIntegerField(null=True, blank=True)
    fechaNacimiento = models.DateField(null=True, blank=True)
    estatura = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    peso = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    estado = models.PositiveSmallIntegerField()
    suelo = models.PositiveSmallIntegerField()
    tipo_bici = models.PositiveSmallIntegerField()
    # tipo_bici = models.ForeignKey(tiposBicicletas, on_delete=models.CASCADE, null=True, blank=True)
    usuario_id = models.OneToOneField(User, on_delete=models.CASCADE)


class lista(models.Model):
    nombre = models.CharField(max_length=45)


class videos(models.Model):
    direccion = models.CharField(max_length=200)
    imagen = models.ImageField(upload_to="proyectoFinal", null=True, blank=True)
    id_usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    id_lista = models.ForeignKey(lista, on_delete=models.CASCADE)


class graficoRuta(models.Model):
    gr_pulsaciones = models.ImageField(upload_to="graficos/ppm", null=True, blank=True)
    gr_cadencia = models.ImageField(upload_to="graficos/rpm", null=True, blank=True)
    gr_temperatura = models.ImageField(upload_to="graficos/temperatura", null=True, blank=True)
    id_ruta = models.OneToOneField(Rutas, on_delete=models.CASCADE, related_name="graficosRuta")
