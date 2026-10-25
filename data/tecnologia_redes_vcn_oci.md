# Guía de arquitectura de redes VCN en Oracle Cloud Infrastructure (OCI)

**Equipo de Plataforma en la Nube** · Guía interna de capacitación · Versión 2

> **Documento de capacitación.** Amplía la introducción a las redes VCN de OCI que usa el equipo. Los conceptos corresponden a los componentes de red de OCI; los nombres de las redes, los rangos de direcciones y la arquitectura del ejemplo son ilustrativos. Antes de configurar un entorno real, consulte la documentación oficial de Oracle, porque los límites y las opciones pueden cambiar.

## 1. Qué es una VCN

La Virtual Cloud Network (VCN) es una red privada, virtual y personalizable que se crea dentro de una región de Oracle Cloud Infrastructure. Funciona de forma parecida a la red de un centro de datos tradicional: tiene rangos de direcciones IP, subredes, tablas de enrutamiento, reglas de firewall y puertas de enlace hacia otras redes.

Una VCN pertenece a un **compartimento** (la unidad de OCI para organizar recursos y permisos) y existe en **una sola región**. Para conectar redes de regiones distintas se necesitan componentes adicionales, que se explican más adelante.

## 2. Rangos de direcciones (CIDR)

Al crear la VCN se le asigna uno o varios bloques de direcciones en notación CIDR, por ejemplo `10.0.0.0/16`. Se recomienda usar rangos privados (los definidos en el RFC 1918: `10.0.0.0/8`, `172.16.0.0/12` y `192.168.0.0/16`).

Buenas prácticas:

- Planear los rangos desde el principio y documentarlos en el inventario de redes del equipo.
- No repetir rangos entre VCN que se vayan a conectar entre sí ni con la red de la oficina: si dos redes usan el mismo rango, el tráfico no se puede enrutar entre ellas.
- Dejar espacio libre para crecer: es más fácil reservar un `/16` y usar una parte que ampliar un rango que quedó corto.

## 3. Subredes

Una VCN se divide en **subredes**. Cada subred tiene su propio bloque CIDR, que debe estar dentro del rango de la VCN y no puede solaparse con otra subred.

- **Subred pública:** los recursos pueden tener una dirección IP pública y, si las reglas lo permiten, recibir tráfico desde internet. Se usa para balanceadores de carga o, en entornos pequeños, para el servidor de una aplicación.
- **Subred privada:** los recursos no pueden tener IP pública. Quedan aislados de internet y solo se alcanzan desde dentro de la VCN o desde redes conectadas. Se usa para bases de datos y servidores internos.

Las subredes pueden ser **regionales** (abarcan todos los dominios de disponibilidad de la región) o **específicas de un dominio de disponibilidad**. Oracle recomienda las subredes regionales porque facilitan la alta disponibilidad.

Que una subred sea pública o privada se decide al crearla y no se puede cambiar después. Si se equivoca la elección, hay que crear una subred nueva.

## 4. Tablas de enrutamiento

Cada subred usa una **tabla de enrutamiento** (*route table*) que dice hacia dónde enviar el tráfico que sale de la VCN. Cada regla tiene un destino (un bloque CIDR o un servicio) y un objetivo (una puerta de enlace).

Ejemplo de tabla para una subred pública:

| Destino | Objetivo | Para qué |
|---|---|---|
| `0.0.0.0/0` | Internet Gateway | Todo el tráfico hacia internet |

Ejemplo de tabla para una subred privada:

| Destino | Objetivo | Para qué |
|---|---|---|
| `0.0.0.0/0` | NAT Gateway | Salir a internet para actualizaciones, sin recibir conexiones |
| Servicios de Oracle en la región | Service Gateway | Llegar a Object Storage sin pasar por internet |

El tráfico entre subredes de la misma VCN no necesita reglas: se enruta automáticamente.

## 5. Puertas de enlace (*gateways*)

- **Internet Gateway:** permite el tráfico en ambos sentidos entre la VCN e internet. Solo lo usan los recursos con IP pública de subredes públicas.
- **NAT Gateway:** permite que los recursos de una subred privada inicien conexiones hacia internet (por ejemplo, para descargar actualizaciones) sin que nadie desde internet pueda iniciar una conexión hacia ellos.
- **Service Gateway:** permite que los recursos de la VCN lleguen a servicios de Oracle de la misma región, como Object Storage, por la red de Oracle y sin salir a internet. Es la opción recomendada para que un servidor privado guarde archivos en un bucket.
- **Dynamic Routing Gateway (DRG):** router virtual que conecta la VCN con la red de la oficina (por VPN de sitio a sitio o FastConnect) y con VCN de otras regiones o de la misma región.
- **Local Peering:** conexión privada entre dos VCN de la misma región, sin pasar por internet.

## 6. Seguridad: Security Lists y Network Security Groups

OCI ofrece dos mecanismos de firewall virtual que se pueden usar juntos:

- **Security Lists (listas de seguridad):** se asocian a la subred y sus reglas aplican a todas las interfaces de red de esa subred.
- **Network Security Groups (NSG):** se asocian a interfaces de red concretas (por ejemplo, solo a las de los servidores web). Permiten reglas más finas y son la opción recomendada para aplicaciones con varios tipos de servidores.

Cada regla define:

- **Dirección:** de entrada (*ingress*) o de salida (*egress*).
- **Origen o destino:** un bloque CIDR, un servicio o, en los NSG, otro NSG.
- **Protocolo y puertos:** por ejemplo TCP 443.
- **Con estado o sin estado:** en una regla **con estado** (*stateful*), la respuesta a una conexión permitida se deja pasar automáticamente. En una regla **sin estado** (*stateless*), hay que crear también la regla para el tráfico de respuesta. La mayoría de las reglas se crean con estado.

Cuando un recurso está cubierto por una Security List y por un NSG, el tráfico se permite si **cualquiera** de los dos lo permite. Por eso hay que revisar ambos al buscar un permiso de más.

> **Advertencia:** una mala configuración en las reglas de entrada es la causa más común de vulnerabilidades en la infraestructura de OCI. La regla que abre el puerto 22 (SSH) a `0.0.0.0/0` es el error más frecuente.

## 7. Componentes por defecto

Al crear una VCN, OCI crea automáticamente una tabla de enrutamiento, una Security List y un conjunto de opciones de DHCP por defecto. La Security List por defecto permite SSH desde cualquier origen. En el equipo esa regla se debe **eliminar o restringir** a las direcciones de la oficina o al servicio Bastion antes de crear cualquier servidor.

El asistente "Crear VCN con conectividad a internet" de la consola crea en un solo paso una subred pública, una privada, un Internet Gateway, un NAT Gateway y un Service Gateway con sus tablas de enrutamiento. Es útil para empezar, pero hay que revisar las reglas que deja abiertas.

## 8. Acceso administrativo con Bastion

Para entrar por SSH a un servidor de una subred privada no se le pone una IP pública. Se usa el servicio **OCI Bastion**, que crea sesiones temporales y auditadas hacia el servidor. Así el puerto 22 nunca queda abierto a internet.

## 9. Arquitectura de ejemplo: una aplicación con Object Storage

Escenario: una aplicación web con interfaz y API corre en una máquina virtual Ampere A1 y guarda documentos y archivos JSON en un bucket de Object Storage.

| Componente | Ubicación | Reglas principales |
|---|---|---|
| VCN `vcn-app` | `10.0.0.0/16` | — |
| Subred pública `sn-publica` | `10.0.1.0/24` | Entrada TCP 443 desde `0.0.0.0/0` hacia el balanceador |
| Balanceador de carga | `sn-publica` | Reenvía al servidor por el puerto de la aplicación |
| Subred privada `sn-app` | `10.0.2.0/24` | Entrada solo desde el NSG del balanceador; sin IP pública |
| Máquina virtual de la aplicación | `sn-app` | Sale por NAT Gateway a la API del modelo de lenguaje y por Service Gateway a Object Storage |
| Bucket de Object Storage | Servicio regional | Privado; acceso por políticas de IAM, no por enlaces públicos |

En un entorno de demostración con pocos recursos se puede simplificar dejando la máquina virtual en una subred pública con una IP pública, siempre que:

- Solo se abran los puertos que la aplicación necesita (por ejemplo, 443) y no el puerto de la base de datos.
- SSH quede restringido a una dirección conocida o se use Bastion.
- El bucket siga siendo privado.

## 10. Lista de verificación antes de publicar

1. Los rangos de la VCN y las subredes están documentados y no se solapan con otras redes.
2. Ninguna regla de entrada abre SSH (22) ni puertos de bases de datos a `0.0.0.0/0`.
3. Los servidores internos están en subredes privadas.
4. La salida a Object Storage usa el Service Gateway.
5. Los buckets son privados y el acceso se da con políticas de IAM.
6. Hay al menos una persona responsable de revisar los NSG y las Security Lists cada mes.

## 11. Errores frecuentes

- Crear la subred como privada y después necesitar una IP pública: hay que crear otra subred.
- Olvidar la regla en la tabla de enrutamiento: el Internet Gateway existe, pero la subred no lo usa y no hay salida a internet.
- Abrir el puerto en el NSG pero no en el firewall del sistema operativo de la máquina virtual (o al revés).
- Usar el mismo rango CIDR en dos VCN que después se quieren conectar.
- Dejar el bucket público "para probar" y olvidar cerrarlo.

## 12. Glosario

- **CIDR:** notación para indicar un rango de direcciones IP, por ejemplo `10.0.1.0/24` (256 direcciones).
- **Compartimento:** contenedor lógico de OCI para organizar recursos y permisos.
- **Dominio de disponibilidad:** uno o más centros de datos aislados dentro de una región.
- **Ingress / egress:** tráfico de entrada / de salida.
- **IAM:** servicio de identidades y permisos de OCI.
- **Stateful / stateless:** regla que recuerda o no recuerda las conexiones para dejar pasar sus respuestas.
