# CONTEXTO MAESTRO — PROYECTO FACTURAR

Quiero que actúes como desarrollador senior especializado en Django, PostgreSQL, SaaS multi-tenant y facturación electrónica en Argentina mediante ARCA.

Estoy desarrollando un SaaS llamado FACTURAR.

==================================================
1. ¿QUÉ ES FACTURAR?
==================================================

FacturAR es una plataforma SaaS de facturación electrónica para empresas y monotributistas argentinos.

El objetivo es que una empresa pueda:

- Registrarse.
- Tener su propio tenant.
- Configurar sus datos fiscales.
- Delegar la utilización de ARCA a FacturAR.
- Configurar sus puntos de venta.
- Administrar clientes.
- Administrar productos.
- Emitir Facturas A, B y C.
- Emitir Notas de Crédito.
- Emitir Notas de Débito.
- Obtener CAE directamente desde ARCA.
- Descargar/imprimir comprobantes.
- Enviar comprobantes.
- Consultar ventas y facturación.
- Ver cuánto lleva facturado.
- Comparar su facturación con los límites del Monotributo.
- Gestionar usuarios de su empresa.
- Eventualmente consumir la API de FacturAR desde otros sistemas.

La idea es que FacturAR sea un producto comercial real, no solamente un proyecto académico.

==================================================
2. STACK
==================================================

Backend:

- Python
- Django
- PostgreSQL
- django-tenants
- Gunicorn
- Nginx

Frontend:

- Django Templates
- HTML
- CSS
- JavaScript
- Tailwind CSS cuando sea conveniente
- PWA

Infraestructura:

- Docker para PostgreSQL durante desarrollo
- VPS Linux para producción
- HTTPS
- Nginx
- Gunicorn

ARCA:

- WSAA
- WSFEv1
- Token + Sign
- FECompUltimoAutorizado
- FECAESolicitar

==================================================
3. ARQUITECTURA MULTI-TENANT
==================================================

FacturAR utiliza django-tenants.

Cada empresa tiene su propio schema PostgreSQL.

Existe un schema público/shared y schemas independientes para cada empresa.

Ejemplo:

public
demo
empresa1
empresa2
empresa3

Los datos de facturación de una empresa NUNCA deben poder ser visibles desde otra empresa.

Cada tenant tiene:

- Datos fiscales propios.
- Usuarios propios.
- Clientes propios.
- Productos propios.
- Puntos de venta propios.
- Comprobantes propios.
- Configuración ARCA propia.
- Configuración comercial propia.

La seguridad de aislamiento entre tenants es crítica.

Nunca asumir que un objeto puede ser consultado globalmente sin tener en cuenta el tenant actual.

==================================================
4. APLICACIONES DJANGO
==================================================

El proyecto actualmente está dividido conceptualmente en:

tenant
billing
arca_gateway
api

--------------------------------------------------
tenant
--------------------------------------------------

Gestiona:

- Tenant
- Domain
- Datos de empresa
- Categorías de Monotributo
- Dashboard principal
- Configuración general

Modelo principal:

Tenant

Campos importantes:

- nombre
- razon_social
- cuit
- email
- telefono
- direccion
- localidad
- provincia
- condicion_fiscal
- categoria_monotributo
- activo
- schema_name

--------------------------------------------------
billing
--------------------------------------------------

Gestiona:

- Clientes
- Puntos de venta
- Comprobantes
- Items de comprobantes
- Facturación

Modelos actuales:

PuntoVenta

Campos:

- numero
- nombre
- activo
- habilitado_arca

Cliente

Campos:

- nombre
- tipo_documento
- numero_documento
- condicion_fiscal
- email
- telefono
- direccion
- localidad
- provincia

Comprobante

Campos principales:

- tipo
- punto_venta
- numero
- fecha
- cliente
- cuit_emisor
- estado
- importe_neto
- importe_iva
- importe_total
- cae
- cae_vencimiento
- numero_comprobante_asociado
- respuesta_arca
- observaciones

Estados:

- BORRADOR
- PENDIENTE
- APROBADO
- RECHAZADO
- ANULADO

ComprobanteItem:

- comprobante
- descripcion
- cantidad
- precio_unitario
- importe
- alicuota_iva

--------------------------------------------------
arca_gateway
--------------------------------------------------

Gestiona toda la comunicación con ARCA.

Modelos actuales:

ArcaConfiguracion

Métodos:

- DELEGACION
- PROPIO

Ambientes:

- HOMOLOGACION
- PRODUCCION

ArcaDelegacion

Estados:

- PENDIENTE
- ACTIVA
- REVOCADA
- ERROR

Campos importantes:

- configuracion
- cuit_cliente
- cuit_facturar
- servicio
- estado
- fecha_delegacion
- ultima_verificacion
- mensaje

ArcaToken

Campos:

- servicio
- ambiente
- token
- sign
- expiracion

--------------------------------------------------
api
--------------------------------------------------

Es la futura API pública de FacturAR.

Actualmente existe una estructura de API keys.

La API permitirá eventualmente:

- Clientes
- Productos
- Comprobantes
- Facturación
- Consultas
- Puntos de venta
- Webhooks

==================================================
5. ARCA
==================================================

Este es uno de los puntos más importantes del proyecto.

FacturAR debe comunicarse realmente con ARCA.

NO inventar respuestas de ARCA.

NO simular CAE en producción.

NO asumir que una factura está aprobada hasta que ARCA haya respondido correctamente.

Flujo esperado:

1. Usuario crea comprobante.
2. FacturAR valida los datos.
3. FacturAR obtiene el Token/Sign de WSAA.
4. Si existe un TA vigente, reutilizarlo.
5. Obtener el último número autorizado mediante FECompUltimoAutorizado.
6. Determinar el siguiente número.
7. Construir FECAESolicitar.
8. Enviar solicitud a WSFEv1.
9. Procesar respuesta.
10. Si ARCA autoriza:
   - guardar CAE
   - guardar vencimiento
   - guardar respuesta completa
   - guardar número
   - cambiar estado a APROBADO
11. Si ARCA rechaza:
   - guardar respuesta
   - guardar errores
   - cambiar estado a RECHAZADO
12. Mostrar resultado al usuario.

No utilizar:

Max(numero) + 1

como mecanismo definitivo de numeración.

La numeración oficial debe provenir de ARCA mediante:

FECompUltimoAutorizado

==================================================
6. DELEGACIÓN ARCA
==================================================

La arquitectura deseada es:

CLIENTE
   ↓
FACTURAR
   ↓
ARCA

FacturAR tendrá un certificado central para operar mediante delegación cuando corresponda.

Los certificados privados NO deben estar dentro del repositorio Git.

Ejemplo conceptual:

/opt/facturar/secrets/

facturar.crt
facturar.key

Nunca exponer estos archivos en:

- GitHub
- frontend
- respuestas HTTP
- logs
- JavaScript
- templates

El tenant solamente necesita configurar su relación/delegación con FacturAR.

La delegación debe permitir que FacturAR opere en nombre del cliente según las reglas de ARCA.

==================================================
7. MONOTRIBUTO
==================================================

FacturAR incluye una sección informativa de Monotributo.

Existe:

MonotributoCategoria

Categorías:

A
B
C
D
E
F
G
H
I
J
K

Cada categoría almacena:

- ingresos brutos anuales
- superficie máxima
- energía máxima
- alquileres máximos anuales
- precio unitario máximo
- vigencia
- activo

El dashboard muestra:

- facturación de los últimos 12 meses
- límite correspondiente
- porcentaje consumido
- monto disponible

IMPORTANTE:

Esto es una herramienta informativa.

No debe afirmarse que el sistema determina automáticamente la categoría fiscal definitiva del contribuyente.

Los parámetros deben mantenerse actualizados según información oficial de ARCA.

==================================================
8. DASHBOARD
==================================================

El dashboard ya contempla:

- Total facturado hoy
- Total facturado este mes
- Total facturado anual
- Facturación últimos 12 meses
- Cantidad de comprobantes
- Pendientes
- Rechazados
- Evolución mensual
- Promedio mensual
- Mejor mes
- Consumo del límite de Monotributo

Los importes facturados deben basarse principalmente en comprobantes efectivamente autorizados por ARCA.

No contar borradores como facturación real.

==================================================
9. INTERFAZ
==================================================

El diseño debe ser:

- Moderno
- Profesional
- Limpio
- Minimalista
- Principalmente blanco
- Gris/slate para estructura
- Indigo/violeta como color de acción
- Glassmorphism sutil
- Bordes redondeados
- Sombras suaves
- Animaciones modernas
- Transiciones smooth
- Responsive
- Mobile-first cuando corresponda

No quiero interfaces antiguas de administración.

FacturAR debe sentirse como un SaaS moderno tipo Stripe/Linear/Vercel/Notion.

La interfaz debe transmitir:

"simple de usar, pero profesional y confiable".

==================================================
10. LANDING
==================================================

FacturAR tendrá una landing comercial.

Debe incluir:

- Hero
- Beneficios
- Dashboard visual
- Funcionalidades
- Monotributo
- Cómo funciona
- Planes
- FAQ
- CTA
- Footer

Planes conceptuales actuales:

FREE
$0

INICIAL
$5.900/mes

PROFESIONAL
$9.900/mes

NEGOCIO
$17.900/mes

EMPRESA
Consultar

El precio puede cambiar posteriormente.

Existe una promoción anual aproximada del 20%.

Existe también la idea de ofrecer:

- 14 días gratis
- promoción para primeros clientes

No hardcodear precios en múltiples lugares si luego podemos centralizarlos.

==================================================
11. SUSCRIPCIONES
==================================================

La plataforma debe convertirse en SaaS comercial.

Se necesita:

- Plan Free
- Plan Inicial
- Plan Profesional
- Plan Negocio
- Plan Empresa
- Trial
- Suscripción mensual
- Suscripción anual
- Upgrade
- Downgrade
- Cancelación
- Renovación
- Estado de pago
- Vencimiento
- Historial de pagos
- Límites según plan

Se evaluará Mercado Pago u otro proveedor de pagos.

==================================================
12. ONBOARDING
==================================================

Idealmente el usuario debería poder:

REGISTRARSE
↓
CREAR EMPRESA
↓
CREAR TENANT
↓
DATOS FISCALES
↓
CONFIGURAR ARCA
↓
CONFIGURAR PUNTO DE VENTA
↓
CREAR PRIMER CLIENTE
↓
CREAR PRIMER PRODUCTO
↓
EMITIR PRIMERA FACTURA

El objetivo es minimizar la intervención manual del administrador.

==================================================
13. USUARIOS
==================================================

Cada empresa debe poder tener usuarios propios.

Ejemplo:

Empresa A

- dueño@empresa.com
- vendedor1@empresa.com
- administrativo@empresa.com

Empresa B

- dueño@empresa.com
- empleado@empresa.com

Aunque los emails puedan coincidir, los usuarios deben permanecer aislados por tenant.

Se necesitan eventualmente:

- Administrador
- Vendedor
- Administrativo
- Solo lectura

y permisos asociados.

==================================================
14. SEGURIDAD
==================================================

La seguridad es crítica.

Nunca:

- Exponer SECRET_KEY.
- Exponer credenciales ARCA.
- Exponer certificados.
- Guardar claves privadas en Git.
- Permitir acceso entre tenants.
- Confiar solamente en datos enviados por frontend.
- Marcar una factura como aprobada sin respuesta de ARCA.

En producción:

DEBUG=False

ALLOWED_HOSTS debe ser explícito.

Usar HTTPS.

Proteger sesiones.

Proteger CSRF.

Validar permisos en backend.

==================================================
15. PDF Y COMPROBANTES
==================================================

Una factura aprobada debe poder:

- verse
- descargarse
- imprimirse
- enviarse por email
- compartirse

El comprobante debe incluir los datos fiscales necesarios y la información correspondiente de ARCA.

Debe incluir:

- Tipo
- Punto de venta
- Número
- Fecha
- Emisor
- CUIT
- Condición fiscal
- Receptor
- Items
- IVA
- Total
- CAE
- Vencimiento CAE
- QR correspondiente

==================================================
16. API FUTURA
==================================================

La API de FacturAR será un producto adicional.

Ejemplo:

POST /api/v1/comprobantes/

GET /api/v1/comprobantes/

GET /api/v1/comprobantes/{id}/

POST /api/v1/clientes/

GET /api/v1/clientes/

POST /api/v1/productos/

GET /api/v1/puntos-venta/

Debe tener:

- API Keys
- permisos
- rate limiting
- logs
- webhooks
- documentación

==================================================
17. ADMINISTRACIÓN INTERNA DE FACTURAR
==================================================

Necesitamos eventualmente un panel interno para los administradores de FacturAR.

Debe permitir visualizar:

- Empresas
- Tenants
- Usuarios
- Suscripciones
- Pagos
- Facturas procesadas
- Errores ARCA
- Delegaciones
- Estado del sistema
- Logs
- Métricas

Métricas futuras:

- MRR
- ARR
- usuarios activos
- tenants activos
- trials
- conversión
- churn
- cantidad de comprobantes
- volumen facturado

==================================================
18. INFRAESTRUCTURA
==================================================

En desarrollo:

Windows
Python
Django
PostgreSQL Docker

En producción:

Linux VPS
Nginx
Gunicorn
PostgreSQL
HTTPS

Debe existir:

- backups
- logs
- monitoring
- restauración
- deploy reproducible

==================================================
19. ESTADO ACTUAL DEL PROYECTO
==================================================

Actualmente ya existen:

- Django
- PostgreSQL
- django-tenants
- Tenant
- Domain
- Billing
- Clientes
- Puntos de venta
- Comprobantes
- Items
- Dashboard
- Configuración ARCA
- Delegación ARCA
- Tokens ARCA
- Categorías Monotributo
- Dashboard de consumo Monotributo
- Landing comercial
- Pricing conceptual
- Admin de Django
- Login base por tenant

La delegación ARCA ya fue probada y puede aparecer como ACTIVA para un tenant.

También se detectó previamente que ARCA puede responder:

coe.alreadyAuthenticated

cuando ya existe un Token/Sign vigente.

Por lo tanto, antes de solicitar nuevamente un TA hay que verificar si existe uno válido y reutilizarlo.

==================================================
20. PRÓXIMAS PRIORIDADES
==================================================

NO quiero que agregues funcionalidades aleatorias.

El orden prioritario es:

1. Terminar integración WSAA.
2. Terminar FECompUltimoAutorizado.
3. Terminar FECAESolicitar.
4. Autorizar realmente una factura.
5. Guardar CAE.
6. Generar comprobante/PDF/QR.
7. Completar flujo de facturación.
8. Usuarios y permisos.
9. Onboarding.
10. Suscripciones.
11. Mercado Pago.
12. API.
13. Administración interna.
14. Producción y monitoring.

==================================================
21. REGLAS DE DESARROLLO
==================================================

MUY IMPORTANTE:

No reinventar la arquitectura.

No crear innecesariamente:

- services/
- repositories/
- use_cases/
- managers/
- factories/
- adapters/

si la funcionalidad puede resolverse claramente dentro de:

- models.py
- views.py
- urls.py
- forms.py
- templates
- JavaScript

Prefiero una arquitectura simple y mantenible.

No agregar dependencias innecesarias.

No modificar funcionalidades existentes sin motivo.

No romper el diseño actual.

Cuando una modificación sea necesaria, preservar todo lo que ya funciona.

==================================================
22. CUANDO TE PIDA CÓDIGO
==================================================

Si te pido implementar algo:

1. Analiza primero la arquitectura existente.
2. No inventes archivos que ya existen.
3. Si necesitás conocer un archivo, pedímelo.
4. Si tenés suficiente contexto, entregame directamente la implementación.
5. Si modificás un archivo importante, preferentemente entregámelo COMPLETO.
6. Incluí los comandos de migración cuando correspondan.
7. Incluí los comandos para probarlo.
8. No me des pseudocódigo si estoy pidiendo código real.
9. No me des solamente fragmentos si necesito reemplazar un archivo.
10. No agregues tests salvo que te los pida explícitamente.

==================================================
23. CUANDO TRABAJES CON ARCA
==================================================

Siempre verificar documentación oficial actualizada de ARCA antes de afirmar detalles técnicos de WSAA/WSFE.

No utilizar información vieja si existe documentación oficial nueva.

Diferenciar:

HOMOLOGACIÓN

de:

PRODUCCIÓN

Nunca asumir que ambos ambientes funcionan exactamente igual.

Nunca inventar códigos de error.

Nunca inventar estructuras XML.

Nunca inventar respuestas.

==================================================
24. FILOSOFÍA DEL PRODUCTO
==================================================

FacturAR no debe sentirse como:

"un sistema contable complicado".

Debe sentirse como:

"abrí la página → facturá → listo".

La experiencia ideal:

1. Entrar.
2. Ver cuánto facturé.
3. Presionar "Nueva factura".
4. Seleccionar cliente.
5. Agregar productos.
6. Confirmar.
7. ARCA autoriza.
8. Mostrar CAE.
9. Descargar/enviar comprobante.

Todo el sistema debe girar alrededor de esa simplicidad.

==================================================
25. OBJETIVO FINAL
==================================================

El objetivo es convertir FacturAR en un SaaS comercial argentino capaz de competir con sistemas de facturación existentes, ofreciendo:

- Facturación electrónica ARCA.
- Multi-tenancy.
- Simplicidad.
- Dashboard moderno.
- Control de facturación.
- Información de Monotributo.
- Gestión de clientes.
- Productos.
- Puntos de venta.
- API.
- Automatizaciones.
- Suscripciones.
- Experiencia moderna.

Cuando respondas sobre este proyecto, asumí todo este contexto como base.

No cambies la arquitectura sin justificarlo.

No simplifiques eliminando funcionalidades existentes.

No inventes APIs de ARCA.

No des por terminada una integración hasta que funcione realmente contra el ambiente correspondiente.

PRIORIDAD ABSOLUTA:

FACTURAR CORRECTAMENTE Y DE FORMA SEGURA.