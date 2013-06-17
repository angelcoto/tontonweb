#!/usr/bin/python
# -*- coding: utf-8 -*-

# tontonstat.py
#       
#  Copyright 2012 Ángel Coto <codiasw@gmail.com>
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

# Descripcion:
# Este programa genera estadísticas a partir de la base de datos de tontonweb
# y las remite por correo al administrador de tontonweb.

# Historial de versión
# 1.0.0: * Versión inicial.
# 1.0.1: * Mejora el formato del reporte de tal manera que sea más estructurado a la vista.
# 1.0.2: * Optimiza la generación de estadísticas de indisponibilidad, al forzar la 
#          utilización de índice por resultado.
#        * Incorpora estadísticas de verificaciones totales, fallidas y tasa de éxito, por mes.
# 1.0.3: * Se modifica el segmento de reporte de indisponibilidad (SegmentoIndisponibilidad)
#          para que el lugar de mostrar el cambio Serie muestre el campo Mensaje (usando variable Causa).
#        * Debido a que el campo Mensaje es almacenado en la bd como Unicode, éste es transformado
#          usando utf-8 previo a la generación del reporte.
#        * Los reportes de estadísticas ya no son enviados al administrador de tontonweb sino que se envían
#          a una dirección designada para este propósito (para_estad, en el archivo ini).
#        * Se modifica el método ModificaReporte para que el 1 de cada mes genere el reporte
#          correspondiente al mes anterior.
# 1.0.4: * El segmento de indisponibilidad ya no incluye los registros cuyo tiempo de indisponibilidad = 0
#        * Se agrega segmento de inestabilidades por día para el mes en curso.
#        * Se crean métodos en la clase reporte, para generar encabezado, notas y pie de reporte.
# 1.1.0: * El nombre del sensor es impreso en mayúscula en el correo de estadísticas.  Esto para dar más realce.
#        * Se agrega al archivo ini sección para identificar la entidad (sección "datos_entidad") a la cual se le presta el servicio.  Esto
#          permite que en el asunto del correo de estadísticas se informe a qué entidad pertenece las estadísticas.
#        * Se incorpora el manejo de exclusiones, es decir mensajes de respuesta de monitoreo que no se deben
#          tomar en cuenta para las estadísticas.  Estos mensajes se definen en el archivo ini en el campo
#          "mensajes_exclusiones".
#        * El informe de estadísticas se produce en HTML.

import os
import smtplib
import sqlite3
from ConfigParser import SafeConfigParser
from time import localtime, strftime, time
from getpass import getpass
from base64 import standard_b64decode, standard_b64encode
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.Header import Header
from socket import gethostname


### Define la versión del programa
Programa = 'tontonstat'
Ver = '1.1.0'
Copyright = 'Copyright (c) 2013 Angel Coto <codiasw@gmail.com>'
CopyrightAlt = 'Copyright (c) 2013 codiasw-tools (codiasw@gmail.com)'
Maquina = gethostname()

### Inicializa variables de mensajes
ErrorLog1 = "{0}\tERROR\tError en la comunicación o autenticación con el servidor de correo"
ErrorLog2 = "{0}\tERROR\tError al intentar enviar el mensaje luego de contactar exitosamente al servidor de correo"
ErrorLog3 = "{0}\tERROR\t{1} finalizó debido a errores en archivo ini"
ErrorLog4 = "{0}\tERROR\t{1} no se pudo conectar a la base de datos {2}"
ErrorLog5 = '{0}\tERROR\t{1} no pudo correr consulta "{2}"'
ErrorLog6 = "{0}\tERROR\t{1} no pudo generar reporte"
ErrorLog7 = "{0}\tERROR\t{1} no pudo leer el archivo {2}"
ErrorLog8 = "{0}\tERROR\t{1} detectó que el campo '{2}' del archivo {3} no tiene tipo correcto o no tiene valor."
ErrorLog9 = "{0}\tERROR\t{1} detectó que '{2}' no es valor esperado para '{3}'."

EventoLog0 = "{0}\tINFORMATIVO\t{1} inició con éxito"
EventoLog3 = "{0}\tINFORMATIVO\t{1} envió exitosamente el reporte de estadísticas a {2}"
EventoLog4 = "{0}\tINFORMATIVO\t{1} no pudo enviar el reporte de estadìsticas"
EventoLog100 = "{0}\tINFORMATIVO\t{1} fue detenido"


class Correo:
	
	def __init__(self, Servidor, Puerto, Cuenta, Pwd = None):
		self.Cuenta = Cuenta
		self.Pwd = Pwd
		self.Servidor = Servidor
		self.Puerto = Puerto
		self.Asunto = Programa + '@' + Maquina.upper() + ': ** Reportando estadísticas'
		self.Mensaje = ''
	
	def CreaAsunto(self, Asunto):
		self.Asunto = Asunto

	def CreaMensaje(self, Mensaje): #Método genérico para cualquier mensaje preelaborado
		self.Mensaje = Mensaje
		
	def EnviarCorreo(self, Remitente, Destinatarios): #Método genérico para enviar correo
		# Construye el mensaje simple (texto y sin adjunto)
		Asunto = self.Asunto.decode('utf-8')
		Asunto = Header(Asunto,'utf-8')
		Mensaje = MIMEMultipart('alternative')
		Mensaje['From'] = Remitente
		Mensaje['To'] = Remitente
		Mensaje['Subject'] = Asunto
		Contenido = MIMEText(self.Mensaje, 'html','utf-8')
		Mensaje.attach(Contenido)

		# Conecta con el servidor de correo
		if self.Servidor == 'smtp.gmail.com':
			try:
				mailServer = smtplib.SMTP(self.Servidor,self.Puerto)
				mailServer.starttls()
				mailServer.login(self.Cuenta, standard_b64decode(self.Pwd))
			except:
				return 1
		else:
			try:
				mailServer = smtplib.SMTP(self.Servidor, self.Puerto)
			#	mailServer.set_debuglevel(True) #Usar en caso de requerir ver comunicación con server
			except:
				return 1
		
		# Envía el mensaje
		try:
			mailServer.sendmail(Remitente, Destinatarios, Mensaje.as_string())
			return 0
		except:
			return 2
		finally:
			mailServer.quit()

class Log:
	
	def __init__(self, Archivo):
		self.Archivo = Archivo
		self.TamanoMaximo = 1048576
	
	def GrabaRegistroLog(self, Registro):
		ArchivoLog = open(self.Archivo, 'a')
		ArchivoLog.write(Registro + '\n')
		ArchivoLog.close()
		if self.VerificaTamano():
			self.RenombraLog()
		
	def VerificaTamano(self):
		if os.path.getsize(self.Archivo) >= self.TamanoMaximo:
			return True
		else:
			return False
		
	def RenombraLog(self):
		Parte1 = os.path.splitext(os.path.basename(self.Archivo))[0]
		Extension = os.path.splitext(os.path.basename(self.Archivo))[1]
		Complemento = hora = strftime("_%Y%m%d_%H%M%S", localtime())
		Nuevonombre = Parte1 + Complemento + Extension
		os.rename(self.Archivo,Nuevonombre)

class Parametros:
	
	def __init__(self, Ini, Log):
		self.ArchivoIni = Ini
		self.Error = False
		self.Log = Log
		
		if os.path.isfile(self.ArchivoIni):
			self.NombreEntidad = self.LeeString('datos_entidad', 'nombre_entidad')
			self.AliasEntidad = self.LeeString('datos_entidad', 'alias_entidad')
			self.Servicios = self.LeeLista('datos_monitoreo', 'servicios')
			self.Nombredb = self.LeeString('datos_log', 'db')
			self.Servidor = self.LeeString('datos_servidor_correo', 'servidor')
			self.Puerto = self.LeeNumerico('datos_servidor_correo', 'puerto')
			self.Cuenta = self.LeeString('datos_servidor_correo', 'cuenta')
			self.De = self.LeeString('datos_correo', 'de')
			self.ParaEstad = self.LeeLista('datos_correo', 'para_estad')
			self.MensajesExclusiones = self.LeeLista('datos_estadisticas', 'mensajes_exclusiones')
		else:
			self.Log.GrabaRegistroLog(ErrorLog7.format(strftime('%Y-%m-%d %H:%M:%S', localtime()), Programa, self.ArchivoIni))
			self.Error = True
		
	def LeeLista(self, seccion, opcion):
		parser = SafeConfigParser()
		parser.read(self.ArchivoIni)
		valor = parser.get(seccion,opcion).strip()
		cadena = ''
		Lista = []
		if valor.strip() <> '':
			for caracter in valor:
				if caracter <> ';':
					cadena = cadena + caracter
				else:
					Lista.append(cadena.strip())
					cadena = ''
			Lista.append(cadena.strip())
			return Lista
		else:
			self.Log.GrabaRegistroLog(ErrorLog8.format(strftime('%Y-%m-%d %H:%M:%S', localtime()),Programa,opcion,self.ArchivoIni))
			self.Error = True
			return False
	
	def LeeString(self, seccion, opcion, valores = None):
		parser = SafeConfigParser()
		parser.read(self.ArchivoIni)
		MiString = parser.get(seccion,opcion)
		MiString = MiString.strip()
		if MiString <> '':
			ValorValido = True
			if valores <> None:
				if MiString not in valores:
					ValorValido = False
			if ValorValido:
				return MiString
			else:
				print(ErrorLog9.format(strftime('%Y-%m-%d %H:%M:%S', localtime()),Programa,MiString,opcion))
				self.Error = True
				return False
		else:
			self.Log.GrabaRegistroLog(ErrorLog8.format(strftime('%Y-%m-%d %H:%M:%S', localtime()),Programa,opcion,self.ArchivoIni))
			self.Error = True
			return False
	
	def LeeNumerico(self, seccion, opcion):
		parser = SafeConfigParser()
		parser.read(self.ArchivoIni)
		Numero = 0
		try:
			Numero = int(parser.get(seccion,opcion))
			return Numero
		except:
			self.Log.GrabaRegistroLog(ErrorLog8.format(strftime('%Y-%m-%d %H:%M:%S', localtime()),Programa,opcion,self.ArchivoIni))
			self.Error = True
			return False

class Db:
	
	def __init__(self, NombreDb, Log):
		self.Db = NombreDb
		self.Error = ''
		self.Resultado = ''
		self.Log = Log
		
	def Conecta(self):
		Conecto = True
		if os.path.isfile(self.Db):
			try:
				self.Conexion = sqlite3.connect(self.Db)
				self.Cursor = self.Conexion.cursor()
			except:
				Conecto = False
		else:
			Conecto = False
		return Conecto
		
	def CorreConsulta(self, Sentencia):
		Corrio = True
		if self.Conecta():
			try:
				self.Cursor.execute(Sentencia)
				self.Resultado = self.Cursor.fetchall()
				self.Conexion.close()
			except:
				self.Log.GrabaRegistroLog(ErrorLog5.format(strftime('%Y-%m-%d %H:%M:%S', localtime()), Programa, Sentencia))
				Corrio = False
		else:
			self.Log.GrabaRegistroLog(ErrorLog4.format(strftime('%Y-%m-%d %H:%M:%S', localtime()), Programa, self.Db))
			Corrio = False
		return Corrio

class Reporte():

	def __init__(self, Db, Log, Exclusiones):
		self.Reporte = ''
		self.Segmento = ''
		self.Db = Db
		self.Error = False
		self.Log = Log
		self.Exclusiones = self.ListaExclusiones(Exclusiones)

	def ListaExclusiones(self, Exclusiones):
		Lista = '('
		for Mensaje in Exclusiones:
			Lista += "'" + Mensaje + "',"
		Lista = Lista[0:len(Lista)-1] #Al final queda una coma, es necesario rehacer la lista sin la coma
		Lista += ')'
		return Lista.decode('utf-8') #Se utilizará sentencias sql y por tanto lo pasamos a unicode

	def Encabezado(self):
		Encabezado = """
		<HTML>
			<HEAD>
				<META CHARSET="utf-8">

			<TABLE ALIGN="CENTER" WIDTH=600PX CELLPADDING=0 CELLSPACING="0" STYLE="COLOR:#FFFFFF; FONT-FAMILY: UBUNTU, TREBUCHET-MS, VERDANA, GENEVA, ARIAL; TEXT-ALIGN:CENTER">
				<TBODY>
					<TR> 
						<TH><img src="https://codiasw-tools.googlecode.com/files/tontonweb_estadisticas_v1.png" WIDTH=599 HEIGHT=55></TH> 
					</TR>
				</TBODY>
			</TABLE>
		"""
		return Encabezado
		
	def Pie(self):
		Pie = """
			</TABLE>
			<TABLE ALIGN="CENTER" WIDTH=600PX CELLPADDING=0 CELLSPACING=0>
				<TBODY>
					<TR BGCOLOR=#FFFFFF> <TD></TD> </TR>
					<TR BGCOLOR=#FFFFFF> <TD></TD> </TR>
					<TR BGCOLOR=#FFFFFF> <TD>Estadísticas generadas por """ + Programa + '-' + Ver + ' (un módulo de tontonweb)' + """</TD> </TR>
					<TR BGCOLOR=#FFFFFF> <TD>""" + CopyrightAlt + """</TD> </TR>
				</TBODY>
			</TABLE>
		</HTML>
		"""
		return Pie

	def ModificaReporte(self, Servicio):

		def SegmentoTitulo():
			self.Reporte += """
			<TABLE ALIGN="CENTER" WIDTH=600PX CELLPADDING=5 CELLSPACING=0 RULES=NONE STYLE="COLOR:#000000; FONT-FAMILY: UBUNTU, TREBUCHET-MS, VERDANA, GENEVA, ARIAL; TEXT-ALIGN:CENTER">
				<THEAD>
					<TR BGCOLOR=#FFFFFF> <TH></TH> </TR>
					<TR BGCOLOR=#FFFFFF> <TH></TH> </TR>
					<TR BGCOLOR=#FFCB3B> <TH>"""
			self.Reporte += Servicio
			self.Reporte +="""</TH> </TR>
					<TR BGCOLOR=#FFFFFF> <TH></TH> </TR>
				</THEAD>
			</TABLE>
			"""
		
		def SegmentoIndisponibilidad(Servicio, Mes):
			tiempo = time()
			CreoSegmento = True

			Sentencia = "select sensor, min(fecha),max(fecha), round((julianday(max(fecha)) - julianday(min(fecha)))*24*60,2) as minutos, count(*) as fallas, serie from log "
			Sentencia += "where +url = " + "'" + Servicio + "'" + " and resultado = 'FALLA' and serie <> 0 and mensaje <> 'Falla Red Local o Proveedor' "
			Sentencia += "and strftime('%Y-%m',fecha) = " + "'" + Mes + "' "
			Sentencia += "and mensaje not in " + self.Exclusiones + " "
			Sentencia += "group by sensor, serie order by sensor, serie" 
			
			self.Segmento = """
			<TABLE ALIGN="CENTER" WIDTH=600PX CELLPADDING=5 CELLSPACING=0 BORDER=0 RULES=ROWS STYLE="FONT-FAMILY: UBUNTU, TREBUCHET-MS, VERDANA, GENEVA, ARIAL">
				<THEAD>
					<TR BGCOLOR=#FFFFFF> <TH COLSPAN=6>Indisponibilidad detectada en el mes """
			self.Segmento +=  Mes
			self.Segmento += """</TH> </TR>
					<TR BGCOLOR=#1E5D9D> 
						<TH> <FONT COLOR=#FFFFFF>Sensor</FONT> </TH> 
						<TH> <FONT COLOR=#FFFFFF>Falla desde</FONT> </TH> 
						<TH> <FONT COLOR=#FFFFFF>Falla hasta</FONT> </TH> 
						<TH> <FONT COLOR=#FFFFFF>Min. indisp.</FONT> </TH> 
						<TH> <FONT COLOR=#FFFFFF>Fallas</FONT> </TH> 
						<TH> <FONT COLOR=#FFFFFF>Causa <A href="https://code.google.com/p/codiasw-tools/wiki/tontonweb_CodigosDeRespuesta">(?)</A></FONT> </TH>
					</TR>
				</THEAD>
				<TBODY>
			"""

			if self.Db.CorreConsulta(Sentencia):
				Suma = 0.0
				
				Tabla = self.Db.Resultado
				for Fila in Tabla:
					if Fila[3] <> 0: #Solo incluye los registros que reportan tiempo de indisponibilidad
						Suma = Suma + Fila[3]
						
						Sentencia = "select mensaje from log where fecha = '" + Fila[1] + "'" #Para buscar el valor de mensaje (que se guardará en Causa)
						if self.Db.CorreConsulta(Sentencia):
							Causa = self.Db.Resultado[0][0].encode('utf-8') #Debido a que en la bd el capo está guardado como unicode, es necesario convertirlo con utf-8
							
							#Forma cada fila en la tabla
							self.Segmento += """<TR BGCOLOR=#FFFFFF ALIGN=CENTER> <TD>""" + str(Fila[0]) + """</TD>"""
							self.Segmento += """<TD>""" + str(Fila[1]) + """</TD>"""
							self.Segmento += """<TD>""" + str(Fila[2]) + """</TD>"""
							self.Segmento += """<TD>""" + str(Fila[3]) + """</TD>"""
							self.Segmento += """<TD>""" + str(Fila[4]) + """</TD>"""
							self.Segmento += """<TD>""" + str(Causa) + """</TD></TR>"""
												
						else:
							CreoSegmento = False
							break
				self.Segmento += """</TBODY>"""
				self.Segmento += """
				<TFOOT>
					<TR BGCOLOR=#1E5D9D> 
						<TH COLSPAN=3><FONT COLOR=#FFFFFF>Total indisponibilidad detectada</FONT> </TH> 
						<TH COLSPAN=2><FONT COLOR=#FFFFFF>""" + str(Suma) + """ minutos</FONT> </TH> 
						<TH></TH>
					</TR>
				</TFOOT>

				</TABLE>
				<TABLE ALIGN="CENTER" WIDTH=600PX CELLPADDING=0 CELLSPACING=0>
					<THEAD>
						<TR BGCOLOR=#FFFFFF> <TH></TH> </TR>
					</THEAD>
				</TABLE>
				"""
				
			else:
				CreoSegmento = False
			tiempo = time() - tiempo
			#print('SegmentoIndisponibilidad ' + Servicio + ' : ' + str(tiempo))
			return CreoSegmento

		def SegmentoRatioExito(Servicio):
			tiempo = time()
			Tabla = []
			CreoSegmento = True
			
			#Sentencia para generar verificaciones por mes
			Sentencia = "select strftime('%Y-%m',fecha) as mes, count(*) as verificaciones from log "
			Sentencia += "where url = '" + Servicio + "' "
			Sentencia += "and mensaje <> 'Falla Red Local o Proveedor' "
			Sentencia += "and mensaje not in " + self.Exclusiones + " "
			Sentencia += "group by strftime('%Y-%m',fecha) "
			Sentencia += "order by strftime('%Y-%m',fecha)"
			
			#Crea la tabla de estadísitcas
			if self.Db.CorreConsulta(Sentencia):
				
				for Fila in self.Db.Resultado:
					Linea = []
					Linea.append(Fila[0]) #Mes
					Linea.append(Fila[1]) #Verificaciones
					
					#Sentencia para obtener fallas en el mes especificado en Fila[0]
					Sentencia = "select count(*) from log where resultado = 'FALLA' and mensaje <> 'Falla Red Local o Proveedor' "
					Sentencia += "and mensaje not in " + self.Exclusiones + " "
					Sentencia += " and +url = '" + Servicio + "' and strftime('%Y-%m',fecha) = '" + Fila[0] +"'"
					if self.Db.CorreConsulta(Sentencia):
						Linea.append(self.Db.Resultado[0][0]) #Fallas
					else:
						CreoSegmento = False
						break
					
					Tasa = round((1-float(Linea[2])/float(Linea[1])) * 100 , 2)
					Linea.append(Tasa) #Tasa
					Tabla.append(Linea)
				
			else:
				CreoSegmento = False
		
			
			if CreoSegmento:
				self.Segmento = """
				<TABLE ALIGN="CENTER" WIDTH=600PX CELLPADDING=5 CELLSPACING=0 BORDER=0 RULES=ROWS STYLE="FONT-FAMILY: UBUNTU, TREBUCHET-MS, VERDANA, GENEVA, ARIAL">
					<THEAD>
						<TR BGCOLOR=#FFFFFF> <TH COLSPAN=4>Tasa de éxito en verificaciones</TH> </TR>
						<TR BGCOLOR=#1E5D9D> 
							<TH> <FONT COLOR=#FFFFFF>Mes</FONT> </TH> 
							<TH> <FONT COLOR=#FFFFFF>Verificaciones</FONT> </TH> 
							<TH> <FONT COLOR=#FFFFFF>Fallas</FONT> </TH> 
							<TH> <FONT COLOR=#FFFFFF>Tasa de éxito (%)</FONT> </TH> 
						</TR>
					</THEAD>
					<TBODY>
				"""
								
				Suma = 0.0
				Contador = 0
				for Fila in Tabla:
					self.Segmento += """<TR BGCOLOR=#FFFFFF ALIGN=CENTER> <TD>""" + str(Fila[0]) + """</TD>"""
					self.Segmento += """<TD>""" + str(Fila[1]) + """</TD>"""
					self.Segmento += """<TD>""" + str(Fila[2]) + """</TD>"""
					self.Segmento += """<TD>""" + str(Fila[3]) + """</TD></TR>"""
					
					Suma += Fila[3]
					Contador += 1

				if Contador <> 0:
					Promedio = Suma/Contador
					Promedio = round(Promedio,2)
				else:
					Promedio = 0.0
				self.Segmento += """</TBODY>"""
				self.Segmento += """
					<THEAD>
						<TR BGCOLOR=#1E5D9D> 
							<TH COLSPAN=3><FONT COLOR=#FFFFFF>Promedio de tasa de éxito</FONT> </TH>
							<TH><FONT COLOR=#FFFFFF>""" + str(Promedio) + """%</FONT> </TH>
						</TR>
					</THEAD>
				</TABLE>
				"""


			tiempo = time() - tiempo
			#print('SegmentoRatioExito ' + Servicio + ' : ' + str(tiempo))
			return CreoSegmento
			
		def SegmentoInestabilidadDiario(Servicio, Mes):
			tiempo = time()
			CreoSegmento = True
			
			# La siguiente sentencia arroja una lista de días (posiblemente repetidos)
			Sentencia = "select strftime('%d',fecha) from log "
			Sentencia += "where resultado = 'FALLA' and mensaje <> 'Falla Red Local o Proveedor' "
			Sentencia += "and +url = '" + Servicio + "' "
			Sentencia += "and strftime('%Y-%m',fecha) = '" + Mes + "' "
			Sentencia += "and mensaje not in " + self.Exclusiones + " "
			Sentencia += "group by strftime('%d',fecha), serie having count(*) = 1"
			
			if self.Db.CorreConsulta(Sentencia):
				Primero = True
				Tabla = [] #Se usa para registrar los días y su cuenta
				for Fila in self.Db.Resultado: #Cuenta las veces que se repiten los días en la lista -> Fallas por día
					if Primero: #Solo pasa por acá el primer elemento de la lista
						Dia = Fila[0]
						Tabla.append([Dia, 1])
						Indice = 0
						Primero = False
					else:
						if Dia == Fila[0]:
							Tabla[Indice][1] += 1
						else:
							Tabla.append([Fila[0], 1])
							Indice += 1
							Dia = Fila[0]
			else:
				CreoSegmento = False
			
			if CreoSegmento:
				self.Segmento = '\n** Inestabilidad del mes ' + Mes + ' ** (3)'
				self.Segmento += '\n---------------------------------------\n'
				self.Segmento += 'Día'.center(19) + '|' + 'Fallas'.center(15)
				self.Segmento += '\n---------------------------------------\n'
				
				for Fila in Tabla:
					self.Segmento += str(Fila[0]).center(18) + '|' + str(Fila[1]).center(15) + '\n'
				self.Segmento += '---------------------------------------\n'
				
			tiempo = time() - tiempo
			#print('SegmentoInestabilidadDiario ' + Servicio + ' : ' + str(tiempo))
			return CreoSegmento

		
			"""
			Es necesario determinar si el día actual es 1 de mes, pues si es así el reporte se genera
			para el mes anterior, de lo contrario se genera para el mes actual.  La función devuelve
			el año-mes para el cual se debe generar el reporte.
			"""
		def MesReporte():
			Fecha = localtime()
			Dia = int(strftime('%d',Fecha))
			Mes = int(strftime('%m',Fecha))
			Anio = int(strftime('%Y',Fecha))
			if Dia == 1:
				if Mes == 1:
					Mes = 12
					Anio = Anio - 1
				else:
					Mes = Mes -1
			AnioMes = str(Anio).zfill(2) + '-' + str(Mes).zfill(2)
			return AnioMes

		SegmentoTitulo()
	
		Mes = MesReporte()	

		if SegmentoIndisponibilidad(Servicio, Mes):
			self.Reporte += self.Segmento + '\n'
		else:
			self.Error = True

		#if SegmentoInestabilidadDiario(Servicio, Mes):
			#self.Reporte += self.Segmento + '\n'
		#else:
			#self.Error = True
			
		if SegmentoRatioExito(Servicio):
			self.Reporte += self.Segmento + '\n'
		else:
			self.Error = True
	
def main():
	
	def HintDeUso():
		print(' Genera y envía estadísticas de tontonweb.\n')
		print(' Uso: python {0} '.format(Programa))
		print(' Este programa es software libre bajo licencia GPLv3.\n')

	def PantallaInicial():
		if os.name == 'posix':
			os.system('clear')
		elif os.name == 'nt':
			os.system('cls')
		else:
			None
		print('{0} {1}. {2}\n'.format(Programa,Ver,Copyright))
	
	def HoraTexto():
		return strftime('%Y-%m-%d %H:%M:%S', localtime())

	def EnviaReporte(Entidad, Reporte):
		MiCorreo.CreaAsunto(Programa + '@' + Maquina.upper() + ': ** Estadísticas para ' + Entidad.upper())
		MiCorreo.CreaMensaje(Reporte)
		
		ResultadoEnvio = MiCorreo.EnviarCorreo(ParametrosIni.De, ParametrosIni.ParaEstad)
		Hora = HoraTexto() #Actualiza la hora para el log de eventos
		if ResultadoEnvio == 0:
			LogServicio.GrabaRegistroLog(EventoLog3.format(Hora, Programa, ParametrosIni.ParaEstad))
		elif ResultadoEnvio == 1:
			LogServicio.GrabaRegistroLog(EventoLog4.format(Hora, Programa))
			LogServicio.GrabaRegistroLog(ErrorLog1.format(Hora))
		else:
			LogServicio.GrabaRegistroLog(EventoLog4.format(Hora, Programa))
			LogServicio.GrabaRegistroLog(ErrorLog2.format(Hora))

	try:

		PantallaInicial()
		
		Nombreerrorlog = 'tontonweb@' + Maquina + '.err'
		LogServicio = Log(Nombreerrorlog) #Para registrar eventos del programa

		Archivoini = 'tontonweb.ini'
		ParametrosIni = Parametros(Archivoini, LogServicio) #Crea el objeto de parámetros

		if not ParametrosIni.Error:
			LogServicio.GrabaRegistroLog(EventoLog0.format(HoraTexto(), Programa))
			Pwd = standard_b64encode(getpass("Password de '" + ParametrosIni.Cuenta + "': "))
			MiCorreo = Correo(ParametrosIni.Servidor, ParametrosIni.Puerto, ParametrosIni.Cuenta, Pwd)
			MiDb = Db(ParametrosIni.Nombredb, LogServicio)
			MiReporte = Reporte(MiDb, LogServicio, ParametrosIni.MensajesExclusiones) #Crea el objeto reporte
			
			for Servicio in ParametrosIni.Servicios:
				MiReporte.ModificaReporte(Servicio)
			if not MiReporte.Error:
				Informe = MiReporte.Encabezado() + MiReporte.Reporte + MiReporte.Pie()
				EnviaReporte(ParametrosIni.NombreEntidad, Informe)
			else:
				LogServicio.GrabaRegistroLog(ErrorLog6.format(HoraTexto(),Programa))
		else:
			LogServicio.GrabaRegistroLog(ErrorLog3.format(HoraTexto(),Programa))

	except(KeyboardInterrupt, SystemExit):
		pass
		LogServicio.GrabaRegistroLog(EventoLog100.format(HoraTexto(), Programa))

if __name__ == '__main__':
	main()
else:
	None
