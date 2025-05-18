import json
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from keras.src.saving import load_model
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

from proyectoFinal.decorator import usuario_no_admin_requerido


# @login_required(login_url='index')
@usuario_no_admin_requerido
def calcular(request):
    if request.method == 'GET':
        return render(request, 'proyectofinalWeb/calcular_dureza.html')
    if request.method == 'POST':
        try:
            ruta_modelo = os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static', 'ficheros', 'RN_TFG_v3.h5')
            modelo = load_model(ruta_modelo)
            desnivel_positivo = int(request.POST.get('desnivel_positivo'))

            desnivel_negativo = int(request.POST.get('desnivel_negativo'))

            longitud = float(request.POST.get('long'))
            suelo = int(request.POST.get('suelo'))
            tipo_bici = int(request.POST.get('tipo_bici'))
            estado = int(request.POST.get('estado'))

            X_new = np.array([[desnivel_positivo, desnivel_negativo, longitud, suelo, tipo_bici, estado]])

            df = pd.read_csv(
                os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static\\ficheros\TrainData_SinIndex.csv'))
            # df = pd.read_csv(os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static', 'ficheros', 'TrainData_SinIndex.csv'))
            X = df.drop(['dificultad'], axis=1).values
            X_scaler = MinMaxScaler()
            X_scaler.fit(X)

            # Escalar los datos para la predicción
            X_new_scaled = X_scaler.transform(X_new)

            # Hacer la predicción
            y_pred = modelo.predict(X_new_scaled)
            pred_clase = int(np.argmax(y_pred, axis=1)[0])
            print("y_pred", y_pred)
            print("pred_clase", pred_clase)

            rutaDiccionario = os.path.join(settings.BASE_DIR, 'proyectoFinal', 'static\\ficheros\diccionarios.json')

            with open(rutaDiccionario, 'r') as f:
                diccionarios_cargados = json.load(f)

            # Acceder a los diccionarios cargados
            diccionario_dif_cargado = diccionarios_cargados['dic_dificultad']
            clase = diccionario_dif_cargado.get(str(pred_clase))
            print(clase)
            # return render(request, "proyectofinalWeb/prediccionDureza.html", {'prediccion': [pred_clase, clase]})
            return JsonResponse({
                'pred_clase': pred_clase,
                'clase': clase,
                'success': True
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
