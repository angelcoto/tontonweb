#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# tontonweb.py
#       
#  Copyright 2012-2013 Ángel Coto <codiasw@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details (http://www.gnu.org/licenses/gpl.txt)
#  

# Descripción:
# Este programa hace una verifiación de URLs para determinar
# si están activos o no.

# Historial de versión
# 1.1.0: * Las notificaciones de indisponibilidad ya no se realizan por cada
#          falla detectada, sino que después de cada n fallas consecutivas.
#        * La finalización del proceso a través de Ctrl+C se produce de manera limpia
#          y queda registrada en log de eventos.
#        * El inicio del programa se realiza en pantalla limpia.
#        * En el correo de inicio se indica los URL a monitorear.
# 1.1.1: * Cambia el formato en que se guardan las fechas en log a años-mes-días.
#        * Se crea una función en la clase Log, para que sea esta la que sirve la
#          hora en formato caracter.
# 1.1.2: * No hay cambio de funcionalidad.  Solo se crean funciones dentro de main()
#          para dar más orden al código.
# 1.2.0: * Se incorpora la identificación de redirección de url y prueba del 
#          url redireccionado.
#        * En el log de monitoreo se incorpora una columna para indicar el url
#          de redirección.
#        * En la petición al servidor se envía el "User-Agent" (IE 9).  Esto hace
#          que algunos sitios no denieguen la petición. 
# 1.2.1: * Corrige error cuando se alcanzan n fallas consecutivas.  Una variable
#          (resultado) no existente era llamada.  La variable correcta es verificacion.
# 1.2.2: * Se modifica para evitar denegación de servicio cuando ejecuta la instrucción
#          "mensaje = httplib.responses[estadourl]  #Obtiene el nombre del mensaje a partir del código"
# 1.2.3: * Se modifica manejo de excepción en función obtieneestadourl.  Ahora se dispara la excepción
#          para cualquier tipo de error y no solo para StandarError.
#        * Se modifica leyenda de la versión.  La versión 1.2.3 se considera estable y deja de ser beta.
# 1.2.4: * Se crea funcionalidad para verificar un sitio de referencia (siempre disponible) cuando se detecta
#          que alguno de los servicios monitoreados produce "Problema de Nombre o Red".  Esto es para identificar
#          si la falla se debe a problemas de conexión local.  Si el sitio de referencia también es inalcanzable,
#          entonces se asume que la falla es por conexión local o nuestro proveedor.
#        * El contador de fallas solo se acumula cuando las fallas no son de origen local.  Esto evita notificar
#          falsas alarmas.
#        * Al nombre del log de eventos se le agrega como sufijo el nombre de la máquina antecedido por @.
# 1.3.0: * Los registros de monitoreo ahora también son grabados en base de datos sqlite3.
#        * En el mensaje de notificación se informa el intervalo entre verificaciones.
#        * En el log de monitoreo se adiciona una columna para identificar bloques de fallas consecutivas.
#          A un bloque de fallas consecutivas se le asigna un mismo timestamp.  Cuando no se identifica falla
#          esta columna lleva valor "0".
# 1.4.0: * Se cambia el mensaje "Problema de Nombre o Red" por "Inalcanzable".  
#        * Se modifica el método de verificación de url (check_url) para detectar, como primer paso, si 
#          es posible resolver el nombre del sitio.  Por lo tanto se crea un nuevo tipo de falla: 
#          "Falla Resolución de Nombre".  Si la verificación de nombre es exitosa, se verifica luego
#          el url utilizando la IP obtenida.
#        * Se modifica la forma de grabación a la bd del campo "mensaje", de manera que el valor sea almacenado
#          como Unicode y así pueda almacenar caracteres con tildes.  Se decodifica usando utf-8.
# 1.4.1: * Incorpora manejo de SIGINT para finalizar el proceso de forma limpia, al igual que como lo hace con Ctrl+C
#        * Se corrige método check_url para que al urlredirecion también se le verifique resolución de nombre y emita
#          el mensaje que corresponde, ya que ante falla de dns para urlredireccion se estaba mandando mensaje Inalcanzable.
# 1.4.1.1: * Incorpora una corrección de concepto en el método check_url.  Cuando no se teían acceso a Internet
#            tontonweb no era capaz de resolver nombre y por tanto el reporte de falla quedaba con Falla Resolución de Nombre,
#            lo cual es incorrecto porque debería ser "Falla Red Local o Proveedor".
#          * Se crea una función para verificar conexión a Internet (checkinternet), la cual utiliza una nueva lógica que le da más 
#            rapidez al código.
#          * Se crea una función para verificar resolución de nombre (checkdns), la cual le da más orden al código del método check_url.
# 1.4.1.2: * Elimina el uso de urllib2 para verificar acceso a internet debido a que con esta librería se descarga la página
#            y no solo los encabezados.
#          * Mejora la función que verifica conexión a Internet y se utilizan dos direcciones de www.google.com

import httplib
import smtplib
import os
import sqlite3
import signal
from time import localtime, strftime, sleep, time
from sys import argv, exit
from email.mime.text import MIMEText
from email.Header import Header
from ConfigParser import SafeConfigParser
from socket import gethostname, gethostbyname
from getpass import getpass
from base64 import standard_b64decode, standard_b64encode
from urlparse import urlparse

### Define la identidad del programa
programa = 'tontonweb'
ver = '1.4.1.2'
copyright = 'Copyright (c) 2012-2013 Ángel Coto <codiasw@gmail.com>'


### Inicializa mensajes
errorconsola1 = "* Error 1: '{0}' no es comando válido."
errorconsola2 = "* Error 2: Error de dato en 'tontonweb.ini': el valor de '{0}' no tiene sintaxis correcta."
errorconsola3 = "* Error 3: Error de tipo en 'tontonweb.ini': '{0}' debe ser {1}."
errorconsola4 = "* Error 4: No existe archivo de base de datos '{0}'."

errorlog1 = "{0}\tERROR\tError en la comunicación o autenticación con el servidor de correo"
errorlog2 = "{0}\tERROR\tError al intentar enviar el mensaje luego de contactar exitosamente al servidor de correo"
errorlog3 = "{0}\tERROR\tError de dato en 'tontonweb.ini': el valor de '{1}' no tiene sintaxis correcta"
errorlog4 = "{0}\tERROR\tError de tipo en 'tontonweb.ini': '{1}' debe ser {2}"
errorlog5 = "{0}\tERROR\tNo existe archivo de base de datos '{1}'"
errorlog6 = "{0}\tERROR\tError al intentar grabar registro de monitoreo en base de datos '{1}'"

evento1 = "{0}\tINFORMATIVO\ttontonweb inició con éxito"
evento2 = "{0}\tINFORMATIVO\ttontonweb no pudo iniciar"
evento3 = "{0}\tINFORMATIVO\tSe notificó el inicio de tontonweb\t\t{1}"
evento4 = "{0}\tINFORMATIVO\tNo fue posible enviar notificación de inicio"
evento5 = "{0}\tINFORMATIVO\tSe notificó indisponibilidad\t{1}\t{2}"
evento6 = "{0}\tINFORMATIVO\tNo fue posible notificar indisponibilidad\t{1}"
evento7 = "{0}\tINFORMATIVO\tSe notificó restablecimiento de servicio\t{1}\t{2}"
evento8 = "{0}\tINFORMATIVO\tNo fue posible notificar restablecimiento\t{1}"
evento9 = "{0}\tINFORMATIVO\ttontonweb finalizó debido a un error"
evento10 = "{0}\tINFORMATIVO\tSe notificó la caída de tontonweb\t\t{1}"
evento11 = "{0}\tINFORMATIVO\tNo fue posible notificar la caída de tontonweb"
evento12 = "{0}\tINFORMATIVO\ttontonweb fue detenido"

mensaje1 = "* Se intentará enviar correo reportando el error."

mensajefalla1 = "Inalcanzable"
mensajefalla2 = "Falla Red Local o Proveedor"
mensajefalla3 = "Falla Resolución de Nombre"

class Log:
	
	def __init__(self):
		self.tamanomaximo = 1048576 #Se define 1MB como tamaño máximo
	
	def renombralog(self,nombre):
		if self.verificatamano(nombre,self.tamanomaximo):
			parte1 = os.path.splitext(os.path.basename(nombre))[0]
			extension = os.path.splitext(os.path.basename(nombre))[1]
			complemento = hora = strftime("_%Y%m%d_%H%M%S", localtime())
			nuevonombre = parte1 + complemento + extension

			os.rename(nombre,nuevonombre)
			return True
		else:
			return False
		
	def verificatamano(self,nombre,tamanomaximo):
		if os.path.getsize(nombre) >= tamanomaximo:
			return True
		else:
			return False
			
	def horastring(self):
		return strftime("%Y-%m-%d %H:%M:%S", localtime())

class Correo:
	
	def __init__(self):
		self.de = []
		self.para = []
		self.paraerror = []
		self.asuntofalla = ''
		self.asuntoerror = ''
		self.cuerpofalla = ''
		self.cuerpoerror = ''
		self.cuerpoinicio = ''
	
	def leede(self):
		self.de = []
		parser = SafeConfigParser()
		parser.read('tontonweb.ini')
		self.de = parser.get('datos_correo','de')
		if self.de.strip() <> '':
			return True
		else:
			return False
	
	def leepara(self):
		self.para = []
		parser = SafeConfigParser()
		parser.read('tontonweb.ini')
		valor = parser.get('datos_correo','para')
		if valor.strip() <> '':
			cadena = ''
			for caracter in valor:
				if caracter <> ';':
					cadena = cadena + caracter
				else:
					self.para.append(cadena.strip())
					cadena = ''
			self.para.append(cadena.strip())
			return True
		else:
			return False
	
	def leeparaerror(self):
		self.paraerror = []
		parser = SafeConfigParser()
		parser.read('tontonweb.ini')
		valor = parser.get('datos_correo','para_admin')
		if valor.strip() <> '':
			cadena = ''
			for caracter in valor:
				if caracter <> ';':
					cadena = cadena + caracter
				else:
					self.paraerror.append(cadena.strip())
					cadena = ''
			self.paraerror.append(cadena.strip())
			return True
		else:
			return False
	
	def creaasuntofalla(self,url,maquina):
		self.asuntofalla = programa + '@' + maquina + ': ** FALLA en la verificación de ' + url
		return self.asuntofalla
	
	def creaasuntoinicio(self,maquina):
		asunto = programa + '@' + maquina + ': ** Se inició el servicio de monitoreo'
		return asunto
	
	def creaasuntoerror(self,maquina):
		self.asuntoerror = programa+ '@' + maquina + ': ** Error en el servicio de monitoreo'
		return self.asuntoerror
	
	def creacuerpofalla(self,url,maquina,mensaje,hora,fallas,intervalo):
		self.cuerpofalla = 'La verificación del sitio ' + url
		self.cuerpofalla = self.cuerpofalla + ' produjo ERROR en las últimas ' + str(fallas) + ' verificaciones.  El sitio podría estar fuera de línea.\n\n'
		
		self.cuerpofalla = self.cuerpofalla + 'Sensor    : ' + maquina + '\n'
		self.cuerpofalla = self.cuerpofalla + 'Hora      : ' + hora + '\n'
		self.cuerpofalla = self.cuerpofalla + 'Mensaje   : ' + mensaje + '\n'
		self.cuerpofalla = self.cuerpofalla + 'Intervalo : ' + str(intervalo/60) + ' (minutos entre verificaciones)\n\n'

		self.cuerpofalla = self.cuerpofalla + 'Para descartar falsa alarma verifique si otro sensor notificó simultáneamente la misma situación.  ' 
		self.cuerpofalla = self.cuerpofalla + 'También puede consultar con el administrador para determinar la condición del sitio.\n\n'
		self.cuerpofalla = self.cuerpofalla +  programa + '-' + ver
		return self.cuerpofalla
	
	def creacuerpoinicio(self,maquina,hora,servicios):
		self.cuerpoinicio = 'El servicio de monitoreo ' + programa + '-' + ver + ' inició.\n\n'
		self.cuerpoinicio = self.cuerpoinicio + 'Sensor: ' + maquina + '\n'
		self.cuerpoinicio = self.cuerpoinicio + 'Hora  : ' + hora + '\n'
		self.cuerpoinicio = self.cuerpoinicio + 'URLs  : ' + str(servicios) + '\n\n'
		self.cuerpoinicio = self.cuerpoinicio + 'La actividad del monitoreo se puede consultar en los log del servicio.'
		return self.cuerpoinicio
	
	def creacuerpoerror(self,maquina,hora):
		self.cuerpoerror = 'El servicio de monitoreo ' + programa + '-' + ver + ' finalizó debido a un error.\n\n'
		self.cuerpoerror = self.cuerpoerror + 'Sensor: ' + maquina + '\n'
		self.cuerpoerror = self.cuerpoerror + 'Hora  : ' + hora + '\n\n'
		self.cuerpoerror = self.cuerpoerror + 'Consulte los mensajes de error en el log de eventos del servicio.'
		return self.cuerpoerror
		
	def enviarcorreo(self,remitente,destinatarios,asunto,contenido,servidor,puerto,pwd):
		# Construye el mensaje simple (texto y sin adjunto)
		asunto = asunto.decode('utf-8')
		asunto = Header(asunto,'utf-8')
		mensaje = MIMEText(contenido,'plain','utf-8')
		mensaje['From'] = remitente
		mensaje['To'] = remitente
		mensaje['Subject'] = asunto
		mensaje = mensaje.as_string()

		# Conecta con el servidor de correo
		if servidor == 'smtp.gmail.com':
			try:
				mailServer = smtplib.SMTP(servidor,puerto)
				mailServer.starttls()
				mailServer.login(remitente, standard_b64decode(pwd))
			except:
				return 1
		else:
			try:
				mailServer = smtplib.SMTP(servidor,puerto)
			#	mailServer.set_debuglevel(True) #Usar en caso de requerir ver comunicación con server
			except:
				return 1
		
		# Envía el mensaje
		try:
			mailServer.sendmail(remitente, destinatarios, mensaje)
			return 0
		except:
			return 2
		finally:
			mailServer.quit()
	
class ServidorDeCorreo:
	
	def __init__(self):
		self.cuenta = ''
		self.pwd = ''
		self.servidor = ''
		self.puerto = ''
		
	def leeservidor(self):
		parser = SafeConfigParser()
		parser.read('tontonweb.ini')
		self.servidor = parser.get('datos_servidor_correo','servidor')
		if self.servidor.strip() <> '':
			return True
		else:
			return False
		
	def leepuerto(self):
		parser = SafeConfigParser()
		parser.read('tontonweb.ini')
		try: #¿El puerto es entero?
			self.puerto = int(parser.get('datos_servidor_correo','puerto'))
			return True
		except:
			return False

	def leecuenta(self):
		parser = SafeConfigParser()
		parser.read('tontonweb.ini')
		self.cuenta = parser.get('datos_servidor_correo','cuenta')
		if self.cuenta.strip() <> '':
			return True
		else:
			return False

	def leepwd(self):
		self.pwd = standard_b64encode(getpass("Password de '" + self.cuenta + "': "))

class Monitor:
	
	def __init__(self):
		self.fallas = []
		self.serie = []
		self.maximofallas = 0
		self.intervalo = 0
		self.registrolog = ''
		self.servicios = []
		self.agente = 'IE 9'
		self.nombredb = ''
		
	def leemaximofallas(self):
		parser = SafeConfigParser()
		parser.read('tontonweb.ini')
		try:
			self.maximofallas = int(parser.get('datos_monitoreo','maximo_fallas'))
			return True
		except:
			return False
			
	def leeintervalo(self):
		parser = SafeConfigParser()
		parser.read('tontonweb.ini')
		try:
			self.intervalo = int(parser.get('datos_monitoreo','minutos_intervalo')) * 60
			return True
		except:
			return False
			
	def leeservicios(self):
		self.servicios = []
		parser = SafeConfigParser()
		parser.read('tontonweb.ini')
		valor = parser.get('datos_monitoreo','servicios')
		cadena = ''
		if valor.strip() <> '':
			for caracter in valor:
				if caracter <> ';':
					cadena = cadena + caracter
				else:
					self.servicios.append(cadena.strip())
					self.fallas.append(0)
					self.serie.append(0)
					cadena = ''
			self.servicios.append(cadena.strip())
			self.fallas.append(0)
			self.serie.append(0)
			return True
		else:
			return False
	
	def leenombredb(self):
		parser = SafeConfigParser()
		parser.read('tontonweb.ini')
		self.nombredb = parser.get('datos_log','db')
		if self.nombredb.strip() <> '':
			return True
		else:
			return False
		
	def check_url(self,url):
		
		def obtieneestadourl(url):
			"""
			Descargamos únicamente el encabezado del URL
			y devolvemos el código de estado del server.
			"""
			host, path = urlparse(url)[1:3] #Extrae el host y el path, del url
			try:
				conn = httplib.HTTPConnection(host,timeout=25)
				conn.putrequest('HEAD', path)
				conn.putheader('User-Agent',self.agente)
				conn.endheaders()
				respuesta = conn.getresponse()
				return respuesta.status, respuesta.reason, respuesta.getheader('location')
			except:
				return None, None, None #No se pudo contactar al destino (problema de red)
		
		def checkinternet():
			hayinternet = True
			estado, mensaje, redirecion = obtieneestadourl('http://74.125.137.147') # www.google.com
			if estado == None: #No respondió el primer sitio
				estado, mensaje, redirecion = obtieneestadourl('http://74.125.140.99') # www.google.com
				if estado == None: #No respondió el segundo sitio
					hayinternet = False
			return hayinternet
		
		def checkdns(url):
			host = urlparse(url)[1] #Extrae el host del url principal
			dnsok = True
			try: #Intenta hace la resolución de nombre
				ipurl = gethostbyname(host) #Obtiene la IP a partir de query a DNS
			except:
				dnsok = False
			return dnsok
			
		"""
		Primer paso: ¿existe salida a Internet?
		"""
		if checkinternet():
			"""
			Segundo paso: Verifica resolución de nombre
			"""
			if checkdns(url): #Si fue posible resolver el nombre
				"""
				Tercer paso: Verifica la accesibilidad al url
				"""
				estadourl, mensaje, urlredireccion = obtieneestadourl(url) #Verifica el estado del url
				
				if estadourl <> None: #No hubo problema para contactar al url
					if urlredireccion <> None: #Se obtuvo urlredireccion

						"""
						Hay sitios cuyo url de redirección no incluye el host, en estos casos es necesario
						construir el url comleto.
						"""
						host2 = urlparse(urlredireccion)[1] #Se obtiene el host del url de redirección
						if host2 == '':
							urlredireccion = url + urlredireccion #Cuando no hay host de url de redirección, se usa el host original

						"""
						Segundo paso (nuevamente): Verifica resolución de nombre para url deredireción
						"""
						if checkdns(urlredireccion):
							"""
							Tercer paso (nuevamente): Verifica accesibilidad al url de redirección
							"""
							estadourl, mensaje, urlredireccion2 = obtieneestadourl(urlredireccion) 
						else:
							estadourl, mensaje = None, mensajefalla3
						
				if mensaje == None: #No fue posible contactar al url
					"""
					Debido a que no logró contactar al sitio se utiliza un url de alta disponibilidad
					como url de referencia
					"""
					if checkinternet():
						mensaje = mensajefalla1 #El sitio de referencia respondió.  No es falla local.  Es falla en la ruta hacia el sitio verificado.
					else:
						mensaje = mensajefalla2 #Falló en ambos sitios, se infiere que es falla de la red local o de nuestro proveedor de Internet.

			else: #Hay falla de DNS
				estadourl, mensaje, urlredireccion = None, mensajefalla3, None

		else: #No hay Internet
			estadourl, mensaje, urlredireccion = None, mensajefalla2, None
		
		codigos_buenos = [httplib.OK, httplib.FOUND, httplib.UNAUTHORIZED, httplib.MOVED_PERMANENTLY]
		return [mensaje, estadourl in codigos_buenos, urlredireccion]
	
	def crearegistrolog(self,url,hora,resultado,verificacion,maquina,intervalo,serie):
		self.registrolog =  hora + '\t' + resultado + '\t' + verificacion[0] + '\t' + url + '\t' + str(verificacion[2]) + '\t' + maquina + '\t' + str(intervalo) + '\t' + str(serie) + '\n'
		return self.registrolog
		
	def grabalogdb(self, url,hora,resultado,verificacion,maquina,intervalo,serie):
		conexion = sqlite3.connect(self.nombredb)
		cursor = conexion.cursor()
		grabaresultado = 'OK'
		try:
			cursor.execute("INSERT INTO log VALUES (?,?,?,?,?,?,?,?)",(hora, resultado, verificacion[0].decode('utf-8'), url, str(verificacion[2]), maquina, intervalo, str(serie)))
			conexion.commit()
			conexion.close()
		except:
			grabaresultado = 'FALLA'
		return grabaresultado
		
	def grabaregistroerr(self,archivo,verboso,mensaje):
		if verboso:
			print(mensaje)
		archivo.write(mensaje+'\n')

def main():
	
	def hintdeuso():
		print(' Monitorea la disponibilidad de sitios web.\n')
		print(' Uso: python {0} [?,-cL, -v]\n'.format(programa))
		print(' Opciones:')
		print('         <ninguna>: Los cambios de configuración son aplicados al reiniciar.')
		print('               -cL: Los cambios de configuración son aplicados en línea.')
		print('                -v: Muestra en consola los mensajes del log de eventos (tontonweb.err).')
		print('                 ?: Muestra esta ayuda.\n')
		print(' Este programa es software libre bajo licencia GPLv3.\n')

	def pantalla_inicial():
		
		if os.name == 'posix':
			os.system('clear')
		elif os.name == 'nt':
			os.system('cls')
		else:
			None
			
		print('{0} {1}. {2}\n'.format(programa,ver,copyright))
		
	def verifica_parametros():
		enlinea = False
		verboso = False
		parametrook = True
		try:
			ar1 = argv[1]
			if argv[1] == '-cL':
				enlinea = True
			elif argv[1] == '-v':
				verboso = True
			else:
				parametrook = False
		except:
			None
			
		if parametrook:
			try:
				ar2 = argv[2]
				if ar2 == '-cL':
					enlinea = True
				elif ar2 == '-v':
					verboso = True
				else:
					parametrook = False
			except:
				None
				
		return parametrook, enlinea, verboso
		
	def lee_primer_segmento_ini():
		hora = log.horastring()
		error = False
		tontonweberr = open(nombreerrorlog,'a') #Abre el archivo de registro de mensajes

		if not monitor.leenombredb(): #Obtiene el servidor de correo
			error = True
			opcion = 'db'
			print(errorconsola2.format(opcion))
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog3.format(hora,opcion))
	
		if not os.path.isfile(monitor.nombredb):
			error = True
			print(errorconsola4.format(monitor.nombredb))
			monitor.grabaregistroerr(tontonweberr,verboso, errorlog5.format(hora, monitor.nombredb))
				
		if not servidorcorreo.leeservidor(): #Obtiene el servidor de correo
			error = True
			opcion = 'servidor'
			print(errorconsola2.format(opcion))
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog3.format(hora,opcion))
	
		if not servidorcorreo.leecuenta(): #Obtiene la cuenta de correo
			error = True
			opcion = 'cuenta'
			print(errorconsola2.format(opcion))
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog3.format(hora,opcion))
		
		if not servidorcorreo.leepuerto(): #Obtiene el puerto
			error = True
			opcion = 'puerto'
			tipo = 'entero'
			print(errorconsola3.format(opcion,tipo))
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog4.format(hora,opcion,tipo))
			
		#Inicializa atributo de correo
		if not correo.leede(): #Obtiene el remitente
			error = True
			opcion = 'de'
			print(errorconsola2.format(opcion))
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog3.format(hora,opcion))

		#Inicializa servicios a verificar
		if not monitor.leeservicios(): #Obtiene los URL
			error = True
			opcion = 'servicios'
			print(errorconsola2.format(opcion))
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog3.format(hora,opcion))
					
		if not error:
			servidorcorreo.leepwd() #Lee el password desde consola
		else:
			monitor.grabaregistroerr(tontonweberr,verboso,evento2.format(hora)) #Registra falla de inicio
			
		tontonweberr.close()
		return error

	def lee_segundo_segmento_ini():
		hora = log.horastring()
		error = False

		tontonweberr = open(nombreerrorlog,'a') #Abre el archivo de registro de mensajes
		# Inicializa atributos del monitor
		if not monitor.leemaximofallas(): #Obtiene el intervalo
			error = True
			opcion = 'maximo_fallas'
			tipo = 'entero'
			print(errorconsola3.format(opcion,tipo))
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog4.format(hora,opcion,tipo))

		if not monitor.leeintervalo(): #Obtiene el intervalo
			error = True
			opcion = 'minutos_intervalo'
			tipo = 'entero'
			print(errorconsola3.format(opcion,tipo))
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog4.format(hora,opcion,tipo))
			
		#Inicializa atributos del correo
		if not correo.leepara(): #Obtiene los destinatarios
			error = True
			opcion = 'para'
			print(errorconsola2.format(opcion))
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog3.format(hora,opcion))
			
		if not correo.leeparaerror(): #Obtiene los destinatarios en caso de error
			error = True
			opcion = 'para_admin'
			print(errorconsola2.format(opcion))
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog3.format(hora,opcion))
			
		tontonweberr.close()
		return error
	
	def envia_correo_inicial():
		hora = log.horastring() #Hora en que inicia
		monitor.grabaregistroerr(tontonweberr,verboso,evento1.format(hora)) #Registra en lo de eventos
		
		resultadocorreo = correo.enviarcorreo(servidorcorreo.cuenta, correo.paraerror, correo.creaasuntoinicio(maquina),\
			correo.creacuerpoinicio(maquina,hora,monitor.servicios), servidorcorreo.servidor, servidorcorreo.puerto, servidorcorreo.pwd)
		hora = log.horastring() #Hora en que finalizó el envío de correo
		
		if resultadocorreo == 0: #El correo se envió con éxito
			monitor.grabaregistroerr(tontonweberr,verboso,evento3.format(hora,correo.paraerror)) #Registra notificación
			
		elif resultadocorreo == 1: #Problema de comunicación o autenticación
			monitor.grabaregistroerr(tontonweberr,verboso,evento4.format(hora)) #Registra fallo en la notificación
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog1.format(hora)) #Registra causa del fallo
			
		else: #Hubo fallas en el envío del mensaje
			monitor.grabaregistroerr(tontonweberr,verboso,evento4.format(hora)) #Registra fallo en la notificación
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog2.format(hora)) #Registra causa del fallo

	def monitorea_servicio(indice):
		verificacion = monitor.check_url(url2check) #Ejecuta la verificación del servicio.  Se obtiene una lista.
		hora = log.horastring() #Hora en que finalizó la verificación del url
		tontonweblog = open('tontonweb.log','a') #Abre el log de monitoreo
		
		if verificacion[1]: #Verificación exitosa
			monitor.fallas[indice] = 0
			monitor.serie[indice] = 0
			tontonweblog.write(monitor.crearegistrolog(url2check,hora,'OK',verificacion,maquina,monitor.intervalo, monitor.serie[indice]))
			if monitor.grabalogdb(url2check,hora,'OK',verificacion,maquina,monitor.intervalo, monitor.serie[indice]) <> 'OK':
				monitor.grabaregistroerr(tontonweberr, verboso, errorlog6.format(hora, monitor.nombredb))
			
		else:
			
			if monitor.serie[indice] == 0:
				monitor.serie[indice] = time() #Se establece un timestamp como identificador de la serie de fallos
			
			#Se registra en log de monitoreo
			tontonweblog.write(monitor.crearegistrolog(url2check,hora,'FALLA',verificacion,maquina,monitor.intervalo, monitor.serie[indice]))
			if monitor.grabalogdb(url2check,hora,'FALLA',verificacion,maquina,monitor.intervalo, monitor.serie[indice]) <> 'OK':
				monitor.grabaregistroerr(tontonweberr, verboso, errorlog6.format(hora, monitor.nombredb))
			
			#El contador de fallas se incrementa solo cuando la falla no es por problema local o de nuestro proveedor
			if verificacion[0] <> mensajefalla2: 
				monitor.fallas[indice] = monitor.fallas[indice] + 1
			
			if monitor.fallas[indice] == monitor.maximofallas:
				#Se notifica la falla vía correo a los indicados en el archivo ini
				asunto = correo.creaasuntofalla(url2check,maquina)
				cuerpo = correo.creacuerpofalla(url2check,maquina,verificacion[0],hora,monitor.fallas[indice], monitor.intervalo)
				resultadocorreo = correo.enviarcorreo(servidorcorreo.cuenta, correo.para, correo.asuntofalla, correo.cuerpofalla, servidorcorreo.servidor, servidorcorreo.puerto, servidorcorreo.pwd)
				hora = log.horastring() #Hora en que finalizó el envío de correo
				
				if resultadocorreo == 0: #El correo se envió con éxito
					monitor.grabaregistroerr(tontonweberr,verboso,evento5.format(hora,url2check,correo.para))
					
				elif resultadocorreo == 1: #El correo se envió con éxito
					monitor.grabaregistroerr(tontonweberr,verboso,evento6.format(hora,url2check))
					monitor.grabaregistroerr(tontonweberr,verboso,errorlog1.format(hora))
					
				else:
					monitor.grabaregistroerr(tontonweberr,verboso,evento6.format(hora,url2check))
					monitor.grabaregistroerr(tontonweberr,verboso,errorlog2.format(hora))
					
				monitor.fallas[indice] = 0
		
		tontonweblog.close() #Cierra el log de monitoreo

	def acciones_error_ini():
		print mensaje1
		
		tontonweberr = open(nombreerrorlog,'a') #Abre el archivo de registro de mensajes

		hora = log.horastring()
		
		if not inicializado:
			monitor.grabaregistroerr(tontonweberr,verboso,evento2.format(hora)) #Registra falla de inicio
		else:
			monitor.grabaregistroerr(tontonweberr,verboso,evento9.format(hora)) #Registra caída
		
		#Envía mensaje al administrador de tontonweb
		asunto = correo.creaasuntoerror(maquina)
		cuerpo = correo.creacuerpoerror(maquina,hora)
		resultadocorreo = correo.enviarcorreo(servidorcorreo.cuenta, correo.paraerror, asunto, cuerpo, servidorcorreo.servidor, servidorcorreo.puerto, servidorcorreo.pwd)
		hora = log.horastring() #Hora en que fué enviado el correo
		
		#Se registrará eventos en log de mensajes

		if resultadocorreo == 0:
			monitor.grabaregistroerr(tontonweberr,verboso,evento10.format(hora,correo.paraerror)) #Se registra notificación de falla
		elif resultadocorreo == 1:
			monitor.grabaregistroerr(tontonweberr,verboso,evento11.format(hora)) #Se registra falla en la notificación
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog1.format(hora)) #Se registra causa
		else:
			monitor.grabaregistroerr(tontonweberr,verboso,evento11.format(hora)) #Se registra falla en la notificación
			monitor.grabaregistroerr(tontonweberr,verboso,errorlog2.format(hora)) #Se registra causa

		tontonweberr.close() #Cierra el archivo de registro de mensajes

	def acciones_de_cierre(*args):
		tontonweberr = open(nombreerrorlog,'a')
		hora = log.horastring() #Hora en que finaliza tontonweb
		monitor.grabaregistroerr(tontonweberr,verboso,evento12.format(hora)) #Registra apagado
		tontonweberr.close()
		exit(0);
	
	signal.signal(signal.SIGINT, acciones_de_cierre) #Para capturar señal -2 en instrucción kill (linux)
	
	try:
	
		pantalla_inicial() #Inicia la aplicación en pantalla limpia
		
		parametrook, enlinea, verboso = verifica_parametros() #Verifica si hay parámetros y si son correctos

		if parametrook:
			
			#Inicialización de variables
			inicializado = False #Para que inicialice los parámetros a partir de 'tontonweb.ini'
			maquina = gethostname() #Nombre del equipo.  Para usarse en las notificaciones por correo
			nombreerrorlog = 'tontonweb@' + maquina + '.err'
			correoinicial = False 

			#Crea objetos 
			log = Log()
			monitor = Monitor()
			correo = Correo()
			servidorcorreo = ServidorDeCorreo()
			
			#Atributos de objetos, que se inicializan una sola vez
			#Inicializa atributos de servidor de correo
			error = lee_primer_segmento_ini() #Si alguno de los valores no se puede leer, devuelve True
			
			fallas = 0 #Inicializa el contador de fallas consecutivas
			while not error:
				
				if enlinea or not inicializado:

					# Atributos de objetos, que se pueden inicializar en línea
					error = lee_segundo_segmento_ini() #Si alguno de los valores no se puede leer, devuelve True

					if not error:
						inicializado = True #Para que no vuelva a leer los valores (cuando se usa sin opción -cL)

				if not error: #Puede iniciar.  No hay errores en 'tontonweb.ini'
				
					tontonweberr = open(nombreerrorlog,'a') #Abre el archivo de registro de mensajes
					
					if not correoinicial: #No se ha generado evento y notificación de inicio
						envia_correo_inicial()
						correoinicial = True

					if os.path.exists('tontonweb.log'): 
						log.renombralog('tontonweb.log') #Verifica el tamaño del archivo.  En caso de exceder el límite, lo renombra
						
					indice = 0 #Usado para recorrer la lista de contadores de fallas
					for url2check in monitor.servicios: #Ejecuta el monitoreo para cada servicio
						monitorea_servicio(indice) #Envia el índice de servicio, para acceso a la lista de contadores de fallas
						indice = indice + 1
					
					tontonweberr.close()#Cierra el archivo de registro de mensajes
					
					sleep(monitor.intervalo) #Espera el tiempo definido.  Luego hace la siguiente ronda de monitoreo
					
				else: #No pudo iniciar. Hubo error de archivo ini.
					acciones_error_ini()

		else:
			hintdeuso()
	except (KeyboardInterrupt):
		acciones_de_cierre()
	
if __name__ == '__main__':
	main()
else:
	main()
