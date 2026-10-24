# Manual operativo de pagos inmediatos y prevención de fraude

**Billetera Nubo** · Código MO-PAG-012 · Versión 2 · Área responsable: Gerencia de Riesgo Operativo y Fraude

> **Documento ficticio de capacitación.** Billetera Nubo no existe. Este manual se escribió para demostrar la plataforma NuevaMente. Los límites, los tiempos internos, los nombres de sistemas y los cargos son inventados. Describe prácticas comunes de la industria; no reemplaza la regulación vigente ni las reglas de ningún sistema de pagos real.

## 1. Objetivo

Explicar cómo funcionan los pagos inmediatos dentro de Billetera Nubo, qué controles los protegen y qué debe hacer cada área cuando un cliente reporta un posible fraude. Está dirigido al personal de servicio al cliente, operaciones, riesgo, cumplimiento y tecnología.

## 2. Conceptos básicos

- **Pago inmediato:** transferencia de dinero entre dos cuentas o billeteras que se acredita al destinatario en segundos, a cualquier hora y cualquier día del año, incluidos festivos.
- **Ordenante:** cliente que envía el dinero.
- **Beneficiario:** persona o comercio que recibe el dinero.
- **Llave:** identificador sencillo asociado a una cuenta, que reemplaza el número de cuenta al enviar dinero. En Nubo una llave puede ser el número de celular, el número de documento, el correo electrónico o un código alfanumérico creado por el cliente. Cada llave apunta a una sola cuenta.
- **Directorio de llaves:** registro que traduce la llave a la cuenta del beneficiario y devuelve su nombre parcialmente oculto (por ejemplo, "Lau** Gó**") para que el ordenante confirme antes de pagar.
- **Irrevocabilidad:** una vez confirmado, el pago inmediato no se puede cancelar desde la aplicación. Cualquier devolución depende de que el beneficiario devuelva el dinero o de un proceso de reclamación.
- **Fraude autorizado:** el propio cliente realiza el pago, pero engañado por un tercero (por ejemplo, una falsa oferta de inversión).
- **Fraude no autorizado:** un tercero realiza el pago sin que el cliente lo sepa, normalmente después de tomar el control de su cuenta.
- **Cuenta mula:** cuenta usada para recibir y mover dinero de origen fraudulento. Su titular puede ser cómplice o una persona engañada que "presta" su cuenta.

## 3. Cómo viaja un pago dentro de Nubo

1. El cliente escribe la llave del beneficiario y el monto en la aplicación.
2. Nubo consulta el directorio de llaves y muestra el nombre parcialmente oculto y la entidad del beneficiario.
3. El motor de reglas antifraude **Centinela** evalúa la operación en menos de 300 milisegundos y devuelve uno de tres resultados: aprobar, pedir autenticación adicional o retener para revisión.
4. Si se pide autenticación adicional, el cliente confirma con biometría o con un código de un solo uso enviado a su dispositivo registrado.
5. El pago se envía al sistema de pagos y se acredita al beneficiario.
6. Ordenante y beneficiario reciben una notificación con el monto, la llave y el número de comprobante.

Todo el recorrido debe terminar en menos de 10 segundos. Si Centinela retiene un pago, el dinero no sale de la cuenta del cliente hasta que un analista lo libere o lo rechace.

## 4. Límites operativos

| Tipo de cliente | Límite por operación | Límite diario | Límite en las primeras 24 horas de un dispositivo nuevo |
|---|---|---|---|
| Cuenta básica | COP 1.500.000 | COP 3.000.000 | COP 300.000 |
| Cuenta verificada | COP 5.000.000 | COP 10.000.000 | COP 500.000 |
| Comercio | COP 20.000.000 | COP 60.000.000 | COP 1.000.000 |

El límite de dispositivo nuevo existe porque la mayoría de las tomas de cuenta empiezan registrando la aplicación en el celular del delincuente. El cliente no puede subir este límite durante las primeras 24 horas, ni siquiera llamando a servicio al cliente.

## 5. Controles preventivos

### 5.1 Autenticación

- Inicio de sesión con biometría o clave de seis dígitos.
- Segundo factor obligatorio para: registrar un dispositivo nuevo, cambiar el correo o el celular, crear o borrar llaves, y pagos que superen el 50 % del límite diario.
- Los códigos de un solo uso vencen a los 3 minutos y nunca los pide el personal de Nubo.

### 5.2 Reglas del motor Centinela

Centinela combina reglas fijas con un puntaje de riesgo de 0 a 100. Algunas señales que aumentan el puntaje:

- Dispositivo, red o ubicación nunca vistos para ese cliente.
- Cambio reciente de celular, correo o clave (últimas 48 horas).
- Primer pago a un beneficiario nuevo por un monto alto.
- Varios pagos seguidos a beneficiarios distintos en pocos minutos.
- Beneficiario con muchas cuentas ordenantes diferentes en el mismo día (patrón de cuenta mula).
- Sesión con señales de control remoto del dispositivo.

| Puntaje | Acción |
|---|---|
| 0 a 39 | Aprobar |
| 40 a 69 | Pedir autenticación adicional y mostrar un aviso de seguridad |
| 70 a 100 | Retener para revisión manual |

### 5.3 Confirmación del beneficiario

Antes de confirmar, la aplicación muestra el nombre parcialmente oculto del beneficiario. Si el cliente paga a un beneficiario nuevo por más de COP 1.000.000, aparece una pausa de 10 segundos con la pregunta: "¿Conoces a esta persona? Nubo nunca te pedirá mover tu dinero a otra cuenta para protegerlo".

## 6. Tipos de fraude más comunes

| Tipo | Cómo funciona | Señal típica | Mensaje para el cliente |
|---|---|---|---|
| Suplantación de la entidad (*vishing*) | Alguien llama diciendo ser de Nubo y pide un código o mover el dinero a una "cuenta segura". | Pago grande a beneficiario nuevo justo después de una llamada. | Nubo nunca pide códigos ni transferencias para proteger tu dinero. |
| *Phishing* o enlaces falsos | Un mensaje con un enlace a una página idéntica a la de Nubo roba la clave. | Inicio de sesión desde un dispositivo nuevo minutos después. | Entra siempre desde la aplicación, no desde enlaces. |
| Cambio de SIM (*SIM swapping*) | El delincuente obtiene un duplicado de la SIM y recibe los códigos del cliente. | El celular del cliente pierde la señal de repente. | Si tu celular se queda sin señal sin motivo, llama a tu operador y a Nubo. |
| Falsa inversión o falso comercio | Se ofrecen ganancias altas o productos muy baratos y se pide pagar por llave. | Pagos repetidos y crecientes al mismo beneficiario. | Desconfía de rentabilidades garantizadas. |
| Cuenta mula | Se ofrece dinero a cambio de "prestar" la cuenta para recibir pagos. | Muchos ordenantes distintos y retiros inmediatos. | Prestar tu cuenta te hace responsable de los movimientos. |

## 7. Procedimiento ante un reporte de fraude

Cuando un cliente reporta un posible fraude por chat, línea telefónica o la opción "Reportar un problema" de la aplicación:

1. **Bloquear primero.** El agente bloquea de inmediato la sesión, los dispositivos y las llaves del cliente. Bloquear es reversible; esperar no lo es.
2. **Registrar el caso** en la herramienta de casos con: fecha y hora del reporte, comprobantes de los pagos, canal del contacto y relato del cliente con sus propias palabras.
3. **Clasificar** el caso como fraude autorizado o no autorizado, según si el cliente realizó o no los pagos.
4. **Avisar a la entidad del beneficiario** mediante el canal de alertas entre entidades en menos de 30 minutos desde el reporte, para que intente congelar los fondos. Cada minuto cuenta: las cuentas mula suelen vaciarse en menos de una hora.
5. **Revisar la cuenta del beneficiario** si también es cliente de Nubo: congelar el saldo recibido y abrir una investigación.
6. **Responder al cliente** con el número de caso y el tiempo estimado de respuesta (máximo 15 días hábiles según la política interna).
7. **Escalar a Cumplimiento** cuando existan señales de lavado de activos, para evaluar el reporte de operación sospechosa ante la autoridad competente (en Colombia, la UIAF).

Lo que el agente **nunca** debe hacer: prometer la devolución del dinero, pedir al cliente sus claves o códigos, ni desbloquear la cuenta sin que el cliente haya cambiado su clave y revisado sus dispositivos.

## 8. Ejemplo práctico

Un sábado a las 9:40 p. m., Laura recibe una llamada de un supuesto asesor de Nubo que le dice que su cuenta fue hackeada y que debe pasar su saldo a una "cuenta de resguardo". A las 9:52 p. m. intenta pagar COP 2.400.000 a una llave que nunca había usado.

- Centinela detecta beneficiario nuevo, monto alto y hora inusual: puntaje 74. **Retiene el pago.**
- Laura recibe el aviso de que su pago está en revisión y el mensaje de que Nubo nunca pide mover dinero para protegerlo.
- Un analista la llama desde la línea oficial, confirma la llamada falsa y rechaza el pago. El dinero nunca sale de la cuenta.
- La llave del beneficiario se marca como sospechosa y se comparte la alerta con su entidad.

Si el puntaje hubiera sido 60, Laura habría tenido que confirmar con biometría. La pausa de 10 segundos y el aviso son la última barrera en el fraude autorizado: por eso el mensaje debe ser claro y no técnico.

## 9. Responsabilidades

- **Servicio al cliente:** bloquear, registrar y orientar al cliente; nunca resolver el caso por su cuenta.
- **Analistas de fraude:** revisar los pagos retenidos en menos de 15 minutos en horario 24/7, gestionar las alertas entre entidades y documentar cada decisión.
- **Riesgo operativo:** ajustar las reglas y los umbrales de Centinela cada mes según los casos confirmados y los falsos positivos.
- **Cumplimiento:** evaluar los casos con señales de lavado de activos y gestionar los reportes ante la autoridad.
- **Tecnología:** mantener la disponibilidad del sistema de pagos (meta 99,9 % mensual) y conservar los registros de cada operación durante el tiempo que exige la política de retención.

## 10. Indicadores

| Indicador | Meta |
|---|---|
| Pagos retenidos revisados en menos de 15 minutos | ≥ 95 % |
| Alertas a la entidad del beneficiario en menos de 30 minutos | ≥ 90 % |
| Falsos positivos (pagos retenidos que eran legítimos) | ≤ 3 % de los pagos retenidos |
| Pérdida por fraude sobre el valor total transado | ≤ 0,02 % mensual |

## 11. Glosario

- **Falso positivo:** pago legítimo que el sistema marcó como sospechoso.
- **Toma de cuenta:** cuando un tercero obtiene el control de la cuenta de un cliente.
- **Segundo factor:** prueba adicional de identidad, además de la clave.
- **Ingeniería social:** manipulación de una persona para que entregue información o haga algo en su contra.
- **Reporte de operación sospechosa (ROS):** reporte que una entidad envía a la autoridad cuando detecta operaciones que podrían estar relacionadas con lavado de activos.
