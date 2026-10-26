# Introducción a la Arquitectura de Redes VCN en OCI

La Virtual Cloud Network (VCN) es una red privada y personalizable configurada en Oracle Cloud Infrastructure. Similar a una red de centro de datos tradicional, la VCN ofrece control total sobre su entorno de red, incluyendo subredes públicas y privadas, tablas de enrutamiento, Internet Gateways, NAT Gateways y Security Lists.

## Componentes Principales

Para diseñar una arquitectura segura en la nube, es vital comprender los siguientes elementos:

1. **Subredes (Subnets):**
   Puedes dividir tu VCN en subredes públicas (accesibles desde internet) y privadas (aisladas del exterior).
   
2. **Gateways:**
   * *Internet Gateway:* Permite el tráfico bidireccional entre la VCN y el internet público.
   * *NAT Gateway:* Permite que los recursos en una subred privada accedan a internet para actualizaciones, sin recibir conexiones entrantes.

3. **Security Lists (Listas de Seguridad):**
   Actúan como un firewall virtual. Se utilizan para el control de tráfico mediante reglas de entrada (ingress) y salida (egress). Definen exactamente qué tipo de datos pueden fluir hacia y desde los recursos de la red.

> Advertencia: Una mala configuración en las reglas de ingress de las Security Lists es la causa más común de vulnerabilidades en la infraestructura de OCI.