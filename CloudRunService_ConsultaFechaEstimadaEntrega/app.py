from operator import contains
from xml.etree.ElementInclude import include
from flask import Flask, request
from flask import jsonify
import requests
import json
from datetime import datetime, timedelta
from google.cloud import storage
import datetime as dt
import re
from datetime import date
import os

app = Flask(__name__)

#####################Habilitar en Local##################################
# path = os.path.abspath(__file__)
# pathSA = os.path.join(os.path.dirname(path), "liv-pro-dig-chatbot.json")
# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = pathSA
########################################################################

def getMes(mes):
    if "EN" in mes or "JAN" in mes:
        return "01"
    if "FEB" in mes:
        return "02"
    if "MAR" in mes:
        return "03"
    if "ABR" in mes or "APR" in mes:
        return "04"
    if "MAY" in mes:
        return "05"
    if "JUN" in mes:
        return "06"
    if "JUL" in mes:
        return "07"
    if "AG" in mes or "AUG" in mes:
        return "08"
    if "SEP" in mes or "SET" in mes:
        return "09"
    if "OCT" in mes:
        return "10"
    if "NOV" in mes:
        return "11"
    if "DEC" in mes or "DIC" in mes:
        return "12"


##################Función no disponible es necesaria la VPN para poder hacer uso de la misma ################
def fechasDeEntregaVPN(trNumber):
    try:
        url = "https://pwasso.liverpool.com.mx:8443/rest/model/com/liverpool/OrderSearchActor/orderSearch?trackingNumber="+trNumber

        payload={}
        headers = {
        'brand': 'LP',
        'channel': 'web',
        'lp-auth-header': 'it8sjpiiDawcbETj8Ls0Qg%3D%3D',
        'Cookie': 'JSESSIONID=pDdPhaL4wxJF6cD_PRSVv5zKlWQYJTvrJ2PgMqdh6JMyA7MFPMJj!1584890370; genero=x; segment=fuero'
        }
        
        result = requests.get(url, headers=headers)
        resultjson = json.loads(result.text)
        statusCode=0
        status=""
        noProductos=0
        products=[]
        fecha = ""
        if resultjson.get('s',None) == "0":
            i=0
            CAN = 0 #Cancelado
            ENR = 0
            FFR = 0 #Fecha Fuera de Rango
            FER = 0 #se agrega para escenario donde unos de los SKUs en pedido tiene fecha futura (Fecha En Rango)
            NINV = 0 #No hay inventario disponible
            NHFEE=0 #No hay Fecha Estimada de Entrega
            CC = 0 #producto en click and collect
            PE = 0 #Pedido Entregado
            for field in resultjson.keys():
                if field == "somsOrder":
                    for product in resultjson["somsOrder"]['commerceItems']:
                        i = i+1
                        if "estimatedDeliveryDate" in product.keys():

                            if "EDDErrorCode" in product.keys():
                                error = product["EDDErrorCode"]
                            else:
                                error = ""

                            try:
                                if product['itemStatus'] == 'Pagado':
                                    product['itemStatus'] = 'Pedido confirmado'

                                if ((error in errors) or ("no es posible mostrar la fecha de entrega" in product["estimatedDeliveryDate"])) and (product['itemStatus'] not in ['Pedido entregado','Pedido en camino','Preparando tu pedido','Pasa al modulo a recoger']):
                                    fecha = ""
                                    # FFR = FFR+1
                                    NINV += 1
                                elif "Pedido entregado" in product["itemStatus"] and deliveryInfo.get('eddMessage',None)=='Tu fecha estimada de entrega se ha modificado.':
                                        fecha = product.get('estimatedDeliveryDate',0)
                                        product["itemStatus"] = deliveryInfo.get('eddMessage',None)
                                    
                                elif "Pasa al modulo a recoger" in product["itemStatus"] and deliveryInfo.get('eddMessage',None) in ['Tu fecha estimada de entrega se ha modificado.',None]:
                                        fecha = product.get('estimatedDeliveryDate',0)
                                
                                elif(product['itemStatus']=='Pedido entregado'):
                                    fecha='Pedido entregado'

                                else:
                                    fecha = "Fecha de Entrega: "  + product["estimatedDeliveryDate"]
                                    dates = product["estimatedDeliveryDate"].upper().split("-")
                                    f = dates[len(dates)-1].strip().split(" ")
                                    d=""
                                    x = datetime.now()
                                    if len(f) == 3:
                                        if getMes(f[2]) == "01" and x.month == 12:
                                            d = f[0]+"-"+getMes(f[2])+"-"+str(x.year+1)
                                        else:
                                            d = f[0]+"-"+getMes(f[2])+"-"+str(x.year)
                                    if len(f) == 5:
                                        d = f[0]+"-"+getMes(f[2])+"-"+f[4]
                                    dateFromString = datetime.strptime(d, "%d-%m-%Y")
                                    if "al modulo a recoger" in product["itemStatus"]:
                                        CC = CC+1
                                    if x.date() <= dateFromString.date():
                                        FER = FER+1
                                    else: #se agrega para escenario donde unos de los SKUs en pedido tiene fecha futura (Fecha En Rango)
                                        FFR = FFR+1
                            except:
                                fecha = ""
                        else:
                            NHFEE = NHFEE+1

                        if product["itemStatus"] == "Cancelado":
                            fecha = " "
                            CAN = CAN + 1
                        # if product["itemStatus"] == "Pedido entregado" or product["itemStatus"] == "Regalo Entregado":
                        #     ENR = ENR + 1
                        producto = {
                            'sku':product["SkuId"],
                            'displayName': product["DisplayName"],
                            'imgURL':product["SmallImage"],
                            'estimatedDeliveryDate':fecha,
                            'status':product["itemStatus"]
                        }
                        products.append(producto)
                elif field == "order":
                    for deliveryInfo in resultjson["order"]['deliveryInfo']:
                        for product in deliveryInfo["packedList"]:   
                            if "EDDErrorCode" in product.keys():
                                error = product["EDDErrorCode"]
                            else:
                                error = ""     
                            errors = ['No contamos con inventario en bodega','Por ahora no es posible mostrar la fecha de entrega.']
                            i = i+1
                            if ("estimatedDeliveryDate" in product.keys()) and (product['estimatedDeliveryDate'] != None):
                                try:
                                    if product['itemStatus'] == 'Pagado':
                                        product['itemStatus'] = 'Pedido confirmado'
                                    if ((error in errors) or ("no es posible mostrar la fecha de entrega" in product["estimatedDeliveryDate"])) and (product['itemStatus'] not in ['Pedido entregado','Pedido confirmado','Pedido entregado','Pedido en camino','Preparando tu pedido','Pasa al modulo a recoger']):
                                        fecha = ""
                                        # FFR = FFR+1
                                        NINV = NINV+1
                                    elif "Pedido entregado" in product["itemStatus"] and deliveryInfo.get('eddMessage',None)=='Tu fecha estimada de entrega se ha modificado.':
                                        fecha = product.get('estimatedDeliveryDate',0)
                                        product["itemStatus"] = deliveryInfo.get('eddMessage',None)
                                    
                                    elif "Pasa al modulo a recoger" in product["itemStatus"] and deliveryInfo.get('eddMessage',None) in ['Tu fecha estimada de entrega se ha modificado.',None]:
                                        fecha = product.get('estimatedDeliveryDate',0)

                                    else:                                        
                                        if "Pedido entregado" in product["itemStatus"]:
                                            PE = PE+1

                                        fecha = "Fecha de Entrega: "  + product["estimatedDeliveryDate"]

                                        if deliveryInfo["eddMessage"] != None:
                                            fecha = deliveryInfo["eddMessage"] + " " +fecha

                                        dates = product["estimatedDeliveryDate"].upper().split("-")
                                        f = dates[len(dates)-1].strip().split(" ")
                                        d=""
                                        x = datetime.now()

                                        if len(f) == 3:
                                            if getMes(f[2]) == "01" and x.month == 12:
                                                d = f[0]+"-"+getMes(f[2])+"-"+str(x.year+1)
                                            else:
                                                d = f[0]+"-"+getMes(f[2])+"-"+str(x.year)

                                        if len(f) == 5:
                                            d = f[0]+"-"+getMes(f[2])+"-"+f[4]

                                        dateFromString = datetime.strptime(d, "%d-%m-%Y")

                                        product['estimatedDeliveryDate']=fecha                                    

                                        if "al modulo a recoger" in product["itemStatus"]: #Clic & collect
                                            CC = CC+1
                                        elif x.date() <= dateFromString.date():
                                            FER = FER+1
                                        elif dateFromString.date() < x.date():
                                            NINV = NINV+1
                                        else: #se agrega para escenario donde unos de los SKUs en pedido tiene fecha futura (Fecha En Rango)
                                            # FFR = FFR+1
                                            FER+=1
                                except:
                                    fecha = ""
                            elif(product['itemStatus']=='Preparando tu Regalo'):
                                NINV = NINV+1
                            elif(product['itemStatus']=='Pasa al modulo a recoger'):
                                pass
                            elif(product["itemStatus"] == "Cancelado"):
                                fecha = ""
                                CAN = CAN + 1
                            else:
                                NHFEE = NHFEE+1
                            # if product["itemStatus"] == "Pedido entregado" or product["itemStatus"] == "Regalo Entregado":
                            #     ENR = ENR + 1
                            producto = {
                                'sku':product["skuID"],
                                'displayName': product["displayName"],
                                'imgURL':product["smallImage"],
                                'estimatedDeliveryDate':fecha,
                                'status':product["itemStatus"]
                            }

                            products.append(producto)
                statusCode=200
                if CAN == i:
                    status = "CAN"
                elif (CAN > 0) and (PE > 0):
                    status = "OK" #Estatus para mandar con asesor y encolar
                elif (CAN > 0) and (PE + CAN == i):
                    status = "asesorPedido" #Estatus para mandar con asesor y encolar
                elif CC == i:
                    status = "CC"
                elif NINV > 0 and CAN>0: #Escenario doonde existe un cancelado y pedido entragado
                    status = "OK"
                elif NINV > 0: #Se agrega para escenario donde no hay inventario disponible
                    status = "NINV"
                elif FER > 0: #se agrega para escenario donde unos de los SKUs en pedido tiene fecha futura (Fecha En Rango)
                    status = "FER"
                elif NHFEE == i:
                    status = "NHFEE"
                elif ENR == i:
                    status = "ENR"
                elif FFR == i:
                    status = "FFR"
                elif ENR + CAN + FFR + NHFEE == i:
                    status = "CANENR"
                elif CAN > 0 or ENR > 0 or FFR > 0 or NHFEE>0:
                    status = "OK" #Se cambio de EP a OK por reglas de CAT
                else:
                    status="OK"
                noProductos=i
        else:
            statusCode=400
            status="NOK"
            noProductos=0
            products=[]
        jsonRaw = {
                'statusCode': statusCode,
                'status':status,
                'noProducts':noProductos,
                'products': products
            }
        return jsonRaw
    except BaseException as error:
        statusCode=401
        status='An exception occurred: {}'.format(error)
        noProductos=0
        products=[]
        jsonRaw = {
                'statusCode': statusCode,
                'status':status,
                'noProducts':noProductos,
                'products': products
            }
        return jsonRaw

def validarCorreo(trNumber):
    expresion_regular = r"(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|\"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*\")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(2(5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"
    return re.match(expresion_regular, trNumber)

def getErrorResponse(error):
    jsonRaw = {
        'fulfillmentMessages': [
            {
            'text': {
                    'text': [
                        '{}'.format(error)
                    ]
                }
            }
        ]
    }
    jsonResponse = app.response_class(
        response=json.dumps(jsonRaw),
        status=400,
        mimetype='application/json'
    )
    return jsonResponse
def botones():
    payload={
    "payload": {

            "content": {
              "interactive": {
                "type": "BUTTON",
                "body": {
                  "text": "¿Hay algo más que pueda hacer por ti?"
                },
                "footer": {
                  "text": "Selecciona la opción deseada"
                },
                "action": {
                  "buttons": [
                    {
                      "id": "postback 1",
                      "type": "BUTTON",
                      "title": "No, gracias"
                    },
                    {
                      "id": "postback 2",
                      "type": "BUTTON",
                      "title": "Menú Mis compras"
                    }
                  ]
                },
                "header": {
                  "url": "",
                  "text": "",
                  "type": ""
                }
              }
            },
            "contentType": "INTERACTIVE"
    }
    }

    return payload
def buttons(buttonOption="Hablar con un asesor", buttonAsesor = 1):
    payload={
    "payload": {

            "content": {
              "interactive": {
                "type": "BUTTON",
                "body": {
                  "text": "¿Hay algo más que pueda hacer por ti?"
                },
                "footer": {
                  "text": "Selecciona la opción deseada"
                },
                "action": {
                  "buttons": [
                    {
                      "id": "postback 1",
                      "type": "BUTTON",
                      "title": "No, gracias"
                    },
                    {
                      "id": "postback 2",
                      "type": "BUTTON",
                      "title": "Menú Mis compras"
                    },
                  ]
                },
                "header": {
                  "url": "",
                  "text": "",
                  "type": ""
                }
              }
            },
            "contentType": "INTERACTIVE"
    }
    }

    if buttonAsesor == 1:
        newButton = {"id": "postback 3","type": "BUTTON","title": f'{buttonOption}'}
        payload['payload']['content']['interactive']['action']['buttons'].append(newButton)
        # for i in payload['payload']['content']['interactive']['action']['buttons']:
        #     print(i)
    return payload

def fechasDeEntregaDialogFlow(trNumber):
    
    resultjson = fechasDeEntregaVPN(trNumber)
    products=[]
    asesor = ""
    flagButtons = 0
    product = {}
    
    try:    
        if resultjson["status"]== "OK" or resultjson["status"]== "FER":
            for product in resultjson["products"]:

                if 'no_disponible' in product["imgURL"]:
                    product["imgURL"]='https://assetspwa.liverpool.com.mx/assets/images/filler_REC.gif'

                producto = {
                    "card": {
                        "title": "*"+product["displayName"] +"*\nCódigo de producto:\n*"+product["sku"]+"*",
                        "subtitle": product["status"]+"\n*"+product["estimatedDeliveryDate"]+"*",
                        "imageUri": product["imgURL"],
                        "buttons": [
                            {
                                "text": "Ver mi pedido",
                                "postback": "https://www.liverpool.com.mx/tienda/users/orderHistory?SearchOrder=true&TrackingNo=0"+trNumber
                            }
                        ]
                    }
                }
                products.append(producto)

            # producto = {
            #     "card": {
            #         "title": "Si aún tienes dudas con la información que te presentamos, por favor *indícanos* en qué te podemos ayudar de acuerdo con las siguientes opciones:\n\n-Conocer fecha de entrega\n-Cancelar pedido\n-Seguimiento a mi devolución\n-Cambio de domicilio\n\nEnvía la palabra *asesor* y después un breve comentario de acuerdo con el menú anterior.\nEn un momento serás atendido",
            #         "subtitle": None,
            #         "imageUri": None,
            #         "buttons": [
            #             {
            #                 "text": None,
            #                 "postback": None
            #             }
            #         ]
            #     }
            # }
            # products.append(producto)

        elif resultjson["status"]== "NOK" and resultjson["noProducts"] == 0:
            if "@" in trNumber:
                if validarCorreo(trNumber)== None:
                    asesor = "tag-CONS PEDIDO"
                    products=[{"text": {"text": ["Lo sentimos, la dirección de correo electrónico que nos compartes no es válida, por favor verifícalo y vuelve a intentar.  Gracias "]}}]
                else:
                    products=[{"text": {"text": ["Gracias por favor compártenos la siguiente información:  fecha, código del producto y monto de tu compra, en un momento un asesor te atenderá"]}}]
                    asesor = "asesor-Seg2Incumplimiento-CONS PEDIDO" #"asesor-Seg1Fecha de entrega-CONS PEDIDO"
            else:
                asesor = "tag-CONS PEDIDO"
                products=[{"text": {"text": ["¡Lo siento! El número de pedido que ingresaste es incorrecto, puedes validarlo en tu ticket o confirmación de compra.\n\nGracias por dejarmos ser parte de tu vida"]}}]
        else:
            ##### Operación normal ########
            # products=[{"text": {"text": ["En un momento un asesor te atendera"]}}]
            # if resultjson["status"]== "FFR":
            #     asesor = "asesor-Seg2Incumplimiento-CONS PEDIDO"
            # else:
            #     asesor = "asesor-Seg1Fecha de entrega-CONS PEDIDO"
            ##### Operación normal ########

            ##### Workaround por saturación de asesores ########
            fileName = 'wa/volumetria_seguimiento_wa.csv'
            bucketName = 'liv-pro-dig-chatbot-bkt01'
            client = storage.Client()
            bucket = client.get_bucket(bucketName)
            blob = bucket.get_blob(fileName)
            pedidos = blob.download_as_string().decode("utf8")

            #pedidos=[]

            # if((resultjson["status"]== "FFR") and ('\n{}\r'.format(trNumber) in pedidos)):
            # pedidos = "local"
            var='\n{}\r'.format(trNumber)
            if('\n{}\r'.format(trNumber) in pedidos):
                products=[{"text": {"text": ["¡Hola!\n\nLamentanos no haber entregado tus compras en el tiempo estimado. Tu pedido se encuentra en proceso de entrega. En un periodo no mayor a 72 hrs. hábiles recibirás tus compras.\n\nAgradecemos tu comprensión y gracias por dejarnos ser parte de tu vida."]}}]
                products.append(buttons(buttonAsesor = 0))
                flagButtons = 1
            else:
                if resultjson["status"]== "CC" or resultjson["status"]== "NINV" or resultjson["status"]== "CAN" or resultjson["status"]== "NHFEE":
                    # products=[{"text": {"text": ["​¡Lo siento!​\nPor ahora no es posible mostrar una fecha de entrega estimada.\n\nEstamos trabajando para poderte brindar la fecha de entrega de tu pedido tan pronto nos sea posible."]}}]
                    if (resultjson["status"]== "NHFEE"):
                        products=[{"text": {"text": ["​¡Lo siento!​\nPor ahora no es posible mostrar una fecha de entrega estimada.\n\nEstamos trabajando para poderte brindar la fecha de entrega de tu pedido tan pronto nos sea posible."]}}]
                    # if (resultjson["status"]== "CC"):
                    #     products=[{"text": {"text": ["​¡Tu pedido está listo!​\n\nTe invitamos a acudir al modulo de click & collect de la tienda seleccionada para recoger tu pedido.\n\n​Gracias por permitirnos ser parte de tu vida."]}}]
                    if (resultjson["status"]== "NINV"):
                        if(trNumber[0]==9):
                            products=[{"text": {"text": ["¡Hola!\n\nGracias por contactarnos, estamos trabajando para poderte brindar la fecha de entrega de tu pedido, tan pronto nos sea posible te contactaremos para coordinar la entrega.\n\n Si requieres mayor información, marca desde tu celular al *7171, opción 2 del menú principal y opción 2 del submenú.\n\n Gracias por dejarnos ser parte de tu vida."]}}]
                    #         # asesor = "asesor-Seg2Incumplimiento-CONS PEDIDO"
                        else:
                            products=[{"text": {"text": ["​¡Lo siento!​\nPor ahora no es posible mostrar una fecha de entrega estimada.\n\nEstamos trabajando para poderte brindar la fecha de entrega de tu pedido tan pronto nos sea posible."]}}]
                            products.append(buttons())
                            flagButtons = 1
                    if (resultjson["status"]== "CAN"):
                        products=[{"text": {"text": ["Estimado cliente\n\nVeo que tu pedido se encuentra cancelado, por lo que te pedimos esperar tu devolución\n\nTu saldo se verá reflejado de la siguiente manera, de acuerdo a tu forma de pago:\n\n- Tarjetas Liverpool y Liverpool Visa en 5 días hábiles.\n- Tarjetas de crédito externas en 5 días hábiles.\n- Monedero digital en 5 días hábiles.\n- Tarjetas de débito BBVA, Citibanamex, BanCoppel y PayPal en 10 días hábiles.\n- Otras tarjetas de débito, pagos referenciados (tiendas de conveniencia) y transferencias electrónicas, tu dinero estará listo en 10 días hábiles para recoger en tienda."]}}]
                        products.append(buttons('Seg Reembolso'))
                        flagButtons = 1
                else: #resultjson["status"] == asesorPedido,
                    jsonRaw = {
                        "followupEventInput": {
                            "name": "asesorpedido",
                            "languageCode": "es",
                            "parameters": {
                                "tagQueue": "SegFechaEntrega"
                            }
                        }
                    }
                    jsonResponse = app.response_class(
                        response=json.dumps(jsonRaw),
                        status=200,
                        mimetype='application/json')
                    return jsonResponse
            ##### Workaround por saturación de asesores ########
        
        if flagButtons == 0:
            products.append(buttons(buttonAsesor=0))

            # if "estimatedDeliveryDate" in product and product["estimatedDeliveryDate"]!='':
            #     rango =int(str(product["estimatedDeliveryDate"]).find("-"))
            #     if rango>0:
            #         lista_fecha =str(product["estimatedDeliveryDate"]).split("-")[1].split(" ")
                    
            #         mes_str = lista_fecha[2].lower()
            #         dia_str = lista_fecha[0].lower()
                    
            #     else:
            #         fecha_list = str(product["estimatedDeliveryDate"]).split(":")[1].strip().split(" ")    
            #         mes_str = fecha_list[2].lower()
                    
            #         dia_str = fecha_list[0].lower()
            #     fecha = date.today()

            #     dia_actual = str(fecha).split("-")[2]
            #     mes_actual = str(fecha).split("-")[1]
            #     if mes_actual.startswith("0") :
            #         mes_actual = int(mes_actual[1])
            #         if dia_actual.startswith("0"):
            #             dia_actual = int(dia_actual[1])
            #         else:       
            #             dia_actual = int(dia_actual)
            #     else:
            #         mes_actual = int(mes_actual)

            #     if dia_str.startswith("0"):
            #         dia_pedido=int(dia_str[1])
            #     else:
            #         dia_pedido=(int(dia_str))
                
            #     meses = {"enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,"julio":7,"agosto":8,"septiembre":9,"octubre":10,"noviembre":11,"diciembre":12}
            #     for i in meses.keys():
            #         if mes_str == i:
                    
            #             mes_pedido = meses.get(i)
            #             break
            #     fecha_entrega=((mes_pedido>=mes_actual) and (dia_pedido>=dia_actual))
            #     if product["status"]!="Pedido entregado" and fecha_entrega:
            #         products.append(botones())
            #     else:
            #         products.append(buttons())
            # else:
            #     products.append(buttons(buttonAsesor=0))


        jsonRaw = {
                    # "fulfillmentText":asesor,
                    "fulfillmentResponse":{"messages": products}
                }
        jsonResponse = app.response_class(
        response=json.dumps(jsonRaw),
        status=200,
        mimetype='application/json'
        )
        return jsonResponse
    except BaseException as error:
        return getErrorResponse(error)


def putTag(p):
    jsonRaw ={
        "fulfillmentText": p,
        "fulfillmentResponse":{"messages": [{"text": {"text": ["En un momento uno de nuestros asesores te atenderá. Debido al alto volumen de solicitudes que estamos recibiendo, nuestro tiempo máximo de respuesta será de 90 minutos"]}}]}
    }
    jsonResponse = app.response_class(
        response=json.dumps(jsonRaw),
        status=200,
        mimetype='application/json'
        )
    return jsonResponse


@app.route('/consultaFEE', methods=['POST'])
def consultaSaldo():
    try:
        if(request.headers['Content-Type'] == 'application/json'):
            content = json.loads(request.get_data())
            if(content != None):
                #pedido = content['pedido']
                pedido = content.get('sessionInfo').get('parameters').get('pedido')      
                p = pedido.split('-')
                if len(pedido) == 10:
                    if p[0] == "asesor":
                        return putTag(pedido)
                    else:
                        return fechasDeEntregaDialogFlow(pedido)
                else:
                    jsonRaw = {
                       "fulfillmentResponse":{"messages": [{"text": {"text": ["¡Lo siento! El número de pedido que ingresaste es incorrecto, puedes validarlo en tu ticket o confirmación de compra.\n\nGracias por dejarmos ser parte de tu vida"]}}]}
                    }
                    jsonRaw['fulfillmentResponse']["messages"].append(buttons('Volver a intentar'))
                    #print("jsonRaw",jsonRaw)
                    jsonResponse = app.response_class(
                    response=json.dumps(jsonRaw),
                    status=200,
                    mimetype='application/json'
                    )
                    return jsonResponse
            return getErrorResponse('No content')
        return getErrorResponse('Not correct Content-Type')
    except BaseException as error:
        # print(request.get_data())
        return getErrorResponse(error)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)