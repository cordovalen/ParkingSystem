db = db.getSiblingDB("dbParking");

// Crear colecciones base del dominio
db.createCollection("tickets");
db.createCollection("rates");

// Índices útiles para búsquedas por codigo, placa y estado
db.tickets.createIndex({ code: 1 }, { unique: true });
db.tickets.createIndex({ plateNumber: 1, status: 1 });
db.tickets.createIndex({ status: 1, entryAt: -1 });

// Insertar configuración inicial de tarifas (si no existe)
if (db.rates.countDocuments() === 0) {
  db.rates.insertMany([
    {
        vehicleType: 0,
        currency: "COP",
        initialFlatHours: 4,
        initialFlatRate: 3000,
        additionalHourOrFractionRate: 2500,
        overnightThresholdHours: 12,
        overnightRatePerNight: 50000,
        overnightMode: "PER_NIGHT",
        active: true
    },
    {
        vehicleType: 1,
        currency: "COP",
        firstHourRate: 1300,
        firstTwoHoursRate: 1500,
        additionalHourOrFractionRate: 1300,
        overnightThresholdHours: 12,
        overnightHourlyRate: 1300,
        overnightMode: "PER_HOUR",
        active: true
    }
  ]);
}

print("Inicialización de parking_db completada correctamente.");