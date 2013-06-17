== REQUERIMIENTOS =

1. Python 2.x
2. Acceso a Internet
3. Cuenta en servidor de correo electrónico


== DETALLE DE ARCHIVOS ==

= Archivos del servicio de monitoreo =
  tontonweb.py: Programa que realiza el monitoreo
  tontonweb.ini: Archivo de parámetros de configuración
  tontonweb.db: Archivo de base de datos sqlite3 en donde se guardan los resultados del monitoreo
  tontonweb.log: Log de los resultados del monitoreo.  Tiene una copia de lo guardado en tontonweb.db. Este archivo es creado por tontonweb.py
  tontonweb@<equipo>.err: Log de eventos del servicio. Es creado por tontonweb.py

= Archivos del servicio de estadísticas =
  tontonstat.py: Programa que genera y envía estadísticas
  tontonweb.ini: Archivo de parámetros de configuración (compartido con tontonweb.py)
  tontonweb.db: Archivo de base de datos sqlite3 en donde se guardan los resultados del monitoreo
  tontonweb@<equipo>.err: Log de eventos del servicio (compartido con tontonweb.py)


== EJECUCIÓN ==

  Previo a la ejecución de tontonweb.py o tontonstat.py, es necesario configurar el servicio colocando
  valores a los parámetros del archivo tontonweb.ini.

= tontonweb.py =

  Inicio del servicio:       
    python tontonweb.py <-v> <-cL>
        -v : Imprime en patanlla las salidas del log de eventos
        -cL: Algunos cambios de configuración se pueden realizar sin detener el servicio.

  Finalización del servicio: 
	Ctrl+C
  
= tontonstat.py =

  Inicio del servicio:
    python tontonstat.py

  Finalización del servicio:
    El servicio finaliza automáticamente al enviar las estadísticas generadas.

 
== HISTORIAL DE CAMBIOS ==

= tontonweb-2.0.1 =

  tontonweb.py 1.4.0:
   * Se cambia el mensaje "Problema de Nombre o Red" por "Inalcanzable".  
   * Se modifica el método de verificación de url (check_url) para detectar, como primer paso, si 
     es posible resolver el nombre del sitio.  Por lo tanto se crea un nuevo tipo de falla: 
     "Falla Resolución de Nombre".  Si la verificación de nombre es exitosa, se verifica luego
     el url utilizando la IP obtenida.
   * Se modifica la forma de grabación a la bd del campo "mensaje", de manera que el valor sea almacenado
     como Unicode y así pueda almacenar caracteres con tildes.  Se decodifica usando utf-8.

  tontonstat.py 1.0.3:
   * Se modifica el segmento de reporte de indisponibilidad (SegmentoIndisponibilidad)
     para que el lugar de mostrar el cambio Serie muestre el campo Mensaje (usando variable Causa).
   * Debido a que el campo Mensaje es almacenado en la bd como Unicode, éste es transformado
     usando utf-8 previo a la generación del reporte.
   * Los reportes de estadísticas ya no son enviados al administrador de tontonweb sino que se envían
     a una dirección designada para este propósito (para_estad, en el archivo ini).
   * Se modifica el método ModificaReporte para que el 1 de cada mes genere el reporte
     correspondiente al mes anterior.

  tontonweb.ini:
   * Se agrega el item para_estad en la sección datos_correo.  Esto es para configurar
     la dirección de correo a la cual se enviarán los reportes de estadísticas.
     
= tontonweb-2.0.2
 
  tontonstat.py 1.0.4:
   * El segmento de indisponibilidad ya no incluye los registros cuyo tiempo de indisponibilidad = 0.
   * Se agrega segmento de inestabilidades por día para el mes en curso.
   * Se crean métodos en la clase reporte, para generar encabezado, notas y pie de reporte.

= tontonweb-2.0.3

  tontonweb.py 1.4.1:
   * Incorpora manejo de SIGINT para finalizar el proceso de forma limpia, al igual que como lo hace con Ctrl+C
   * Se corrige la función que verifica el url de redirección, para que también verifique resolución de nombre para el urlredireccion

  tontonweb.py 1.4.1.1:
   * Incorpora una corrección de concepto en el método check_url.  Cuando no se teían acceso a Internet
     tontonweb no era capaz de resolver nombre y por tanto el reporte de falla quedaba con "Falla Resolución de Nombre",
     lo cual es incorrecto porque debería ser "Falla Red Local o Proveedor".
   * Se crea una función para verificar conexión a Internet (checkinternet), la cual utiliza una nueva lógica que le da más 
     rapidez al código.
   * Se crea una función para verificar resolución de nombre (checkdns), la cual le da más orden al código del método check_url.

  tontonweb.py 1.4.1.2:
   * Elimina el uso de urllib2 para verificar acceso a internet debido a que con esta librería se descarga la página
     y no solo los encabezados.
   * Mejora la función que verifica conexión a Internet y se utilizan dos direcciones de www.google.com

= tontonweb-2.1.0

  tontonstat.py 1.1.0:
   * El nombre del sensor es impreso en mayúscula en el correo de estadísticas.  Esto para dar más realce.
   * Se agrega al archivo ini sección para identificar la entidad (sección "datos_entidad") a la cual se le presta el servicio.  Esto
     permite que en el asunto del correo de estadísticas se informe a qué entidad pertenece las estadísticas.
   * Se incorpora el manejo de exclusiones, es decir mensajes de respuesta de monitoreo que no se deben
     tomar en cuenta para las estadísticas.  Estos mensajes se definen en el archivo ini en el campo "mensajes_exclusiones".
   * El informe de estadísticas se produce en HTML.

