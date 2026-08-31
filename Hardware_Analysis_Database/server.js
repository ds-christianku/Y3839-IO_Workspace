const express = require('express');
const fs = require('fs');
const path = require('path');
const os = require('os');
const multer = require('multer');
const sqlite3 = require('sqlite3').verbose();

const app = express();
const port = process.env.PORT || 3000;
const host = process.env.HOST || '0.0.0.0';
const dbPath = path.join(__dirname, 'hardware_analysis.db');
const uploadDir = path.join(__dirname, 'uploads');
const db = new sqlite3.Database(dbPath);

fs.mkdirSync(uploadDir, { recursive: true });

const upload = multer({
  storage: multer.diskStorage({
    destination(req, file, cb) {
      cb(null, uploadDir);
    },
    filename(req, file, cb) {
      const ext = path.extname(file.originalname || '').toLowerCase();
      const safeExt = ext || '.jpg';
      const uniqueName = `${Date.now()}-${Math.round(Math.random() * 1e9)}${safeExt}`;
      cb(null, uniqueName);
    }
  })
});

// Create a table for all delivery entries if it does not exist yet.
db.serialize(() => {
  db.run(`
    CREATE TABLE IF NOT EXISTS intake_entries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      area TEXT NOT NULL,
      serial_number TEXT NOT NULL,
      hardware_version TEXT,
      firmware_on_delivery TEXT NOT NULL,
      firmware_version TEXT,
      fpga_version TEXT,
      oem_version TEXT,
      golden_version TEXT,
      g1_version TEXT,
      g2_version TEXT,
      g3_version TEXT,
      delivery_date TEXT NOT NULL,
      ticket_number TEXT NOT NULL,
      ticket_error_description TEXT NOT NULL,
      sensor_generation TEXT,
      sensor_brand TEXT,
      remote_type TEXT,
      remote_ae_sensor_detected TEXT,
      device_manager_name TEXT,
      sensor_cable_inspection TEXT,
      sensor_g1_detected TEXT,
      sensor_g2_detected TEXT,
      sensor_g3_detected TEXT,
      sensor_path_fpga_check TEXT,
      flashdump_file_path TEXT,
      other_checks TEXT,
      error_cause TEXT,
      current_consumption TEXT,
      current_consumption_unit TEXT,
      pc_led_state TEXT,
      pc_led_state_other TEXT,
      board_power_supply_check TEXT,
      micro_b_damaged TEXT,
      usb_c_damaged TEXT,
      micro_b_damage_image TEXT,
      usb_c_damage_image TEXT,
      created_at TEXT NOT NULL,
      windows_username TEXT NOT NULL
    )
  `);

  // Add missing columns for existing database files created before these fields existed.
  db.all('PRAGMA table_info(intake_entries)', (pragmaErr, columns) => {
    if (pragmaErr) {
      console.error('Fehler beim Lesen der Tabellenspalten:', pragmaErr.message);
      return;
    }

    const columnNames = new Set(columns.map((column) => column.name));

    if (!columnNames.has('micro_b_damaged')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN micro_b_damaged TEXT');
    }

    if (!columnNames.has('usb_c_damaged')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN usb_c_damaged TEXT');
    }

    if (!columnNames.has('micro_b_damage_image')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN micro_b_damage_image TEXT');
    }

    if (!columnNames.has('usb_c_damage_image')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN usb_c_damage_image TEXT');
    }

    if (!columnNames.has('current_consumption')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN current_consumption TEXT');
    }

    if (!columnNames.has('current_consumption_unit')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN current_consumption_unit TEXT');
    }

    if (!columnNames.has('pc_led_state')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN pc_led_state TEXT');
    }

    if (!columnNames.has('pc_led_state_other')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN pc_led_state_other TEXT');
    }

    if (!columnNames.has('board_power_supply_check')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN board_power_supply_check TEXT');
    }

    if (!columnNames.has('remote_ae_sensor_detected')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN remote_ae_sensor_detected TEXT');
    }

    if (!columnNames.has('device_manager_name')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN device_manager_name TEXT');
    }

    if (!columnNames.has('sensor_cable_inspection')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN sensor_cable_inspection TEXT');
    }

    if (!columnNames.has('sensor_g1_detected')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN sensor_g1_detected TEXT');
    }

    if (!columnNames.has('sensor_g2_detected')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN sensor_g2_detected TEXT');
    }

    if (!columnNames.has('sensor_g3_detected')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN sensor_g3_detected TEXT');
    }

    if (!columnNames.has('sensor_path_fpga_check')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN sensor_path_fpga_check TEXT');
    }

    if (!columnNames.has('flashdump_file_path')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN flashdump_file_path TEXT');
    }

    if (!columnNames.has('other_checks')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN other_checks TEXT');
    }

    if (!columnNames.has('error_cause')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN error_cause TEXT');
    }

    if (!columnNames.has('firmware_version')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN firmware_version TEXT');
    }

    if (!columnNames.has('fpga_version')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN fpga_version TEXT');
    }

    if (!columnNames.has('oem_version')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN oem_version TEXT');
    }

    if (!columnNames.has('golden_version')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN golden_version TEXT');
    }

    if (!columnNames.has('g1_version')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN g1_version TEXT');
    }

    if (!columnNames.has('g2_version')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN g2_version TEXT');
    }

    if (!columnNames.has('g3_version')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN g3_version TEXT');
    }

    if (!columnNames.has('hardware_version')) {
      db.run('ALTER TABLE intake_entries ADD COLUMN hardware_version TEXT');
    }
  });
});

app.use(express.json());
app.get('/input', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});
app.get('/input.html', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});
app.get('/output', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'output.html'));
});
app.get('/output.html', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'output.html'));
});
app.get('/auswertung.html', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'output.html'));
});
app.use(express.static(path.join(__dirname, 'public')));
app.use('/uploads', express.static(uploadDir));

app.get('/api/intake/by-serial/:serialNumber', (req, res) => {
  const serialNumber = String(req.params.serialNumber || '').trim();

  if (!serialNumber) {
    return res.status(400).json({ error: 'Seriennummer fehlt.' });
  }

  const query = `
    SELECT
      area,
      serial_number,
      hardware_version,
      firmware_on_delivery,
      firmware_version,
      fpga_version,
      oem_version,
      golden_version,
      g1_version,
      g2_version,
      g3_version,
      delivery_date,
      ticket_number,
      ticket_error_description,
      sensor_generation,
      sensor_brand,
      remote_type,
      remote_ae_sensor_detected,
      device_manager_name,
      sensor_cable_inspection,
      sensor_g1_detected,
      sensor_g2_detected,
      sensor_g3_detected,
      sensor_path_fpga_check,
      flashdump_file_path,
      other_checks,
      error_cause,
      current_consumption,
      current_consumption_unit,
      pc_led_state,
      pc_led_state_other,
      board_power_supply_check,
      micro_b_damaged,
      usb_c_damaged,
      micro_b_damage_image,
      usb_c_damage_image
    FROM intake_entries
    WHERE serial_number = ?
    ORDER BY datetime(created_at) DESC, id DESC
    LIMIT 1
  `;

  db.get(query, [serialNumber], (err, row) => {
    if (err) {
      return res.status(500).json({ error: 'Fehler beim Laden der Daten.' });
    }

    if (!row) {
      return res.json({ found: false });
    }

    return res.json({ found: true, entry: row });
  });
});

app.get('/api/intake/overview', (req, res) => {
  const query = `
    SELECT
      id,
      area,
      serial_number,
      hardware_version,
      firmware_on_delivery,
      firmware_version,
      fpga_version,
      oem_version,
      golden_version,
      g1_version,
      g2_version,
      g3_version,
      delivery_date,
      ticket_number,
      ticket_error_description,
      sensor_generation,
      sensor_brand,
      remote_type,
      remote_ae_sensor_detected,
      device_manager_name,
      sensor_cable_inspection,
      sensor_g1_detected,
      sensor_g2_detected,
      sensor_g3_detected,
      sensor_path_fpga_check,
      flashdump_file_path,
      other_checks,
      error_cause,
      current_consumption,
      current_consumption_unit,
      pc_led_state,
      pc_led_state_other,
      board_power_supply_check,
      micro_b_damaged,
      usb_c_damaged,
      micro_b_damage_image,
      usb_c_damage_image,
      created_at,
      windows_username
    FROM intake_entries
    ORDER BY area ASC, datetime(created_at) DESC, id DESC
  `;

  db.all(query, [], (err, rows) => {
    if (err) {
      return res.status(500).json({ error: 'Fehler beim Laden der Uebersicht.' });
    }

    return res.json({ entries: rows });
  });
});

app.post('/api/intake', upload.fields([
  { name: 'microBDamageImage', maxCount: 1 },
  { name: 'usbCDamageImage', maxCount: 1 },
  { name: 'flashDumpUpload', maxCount: 1 }
]), (req, res) => {
  const {
    area,
    serialNumber,
    hardwareVersion,
    firmwareVersion,
    fpgaVersion,
    oemVersion,
    goldenVersion,
    g1Version,
    g2Version,
    g3Version,
    deliveryDate,
    ticketNumber,
    ticketErrorDescription,
    sensorGeneration,
    sensorBrand,
    remoteType,
    remoteAeSensorDetected,
    deviceManagerName,
    sensorCableInspection,
    sensorG1Detected,
    sensorG2Detected,
    sensorG3Detected,
    sensorPathFpgaCheck,
    otherChecks,
    errorCause,
    currentConsumption,
    currentConsumptionUnit,
    pcLedState,
    pcLedStateOther,
    boardPowerSupplyCheck,
    microBDamaged,
    usbCDamaged
  } = req.body;

  if (!area || !serialNumber) {
    return res.status(400).json({ error: 'Bereich und Seriennummer sind Pflichtfelder.' });
  }

  if (area !== 'sensor' && area !== 'remote') {
    return res.status(400).json({ error: 'Ungueltiger Bereich.' });
  }

  const firmwareOnDelivery = area === 'sensor'
    ? `Firmware Version: ${firmwareVersion || ''}; OEM: ${oemVersion || ''}`
    : `Firmware Version: ${firmwareVersion || ''}; FPGA Version: ${fpgaVersion || ''}; Golden: ${goldenVersion || ''}; G1: ${g1Version || ''}; G2: ${g2Version || ''}; G3: ${g3Version || ''}`;

  const needsDeviceName = area === 'remote' && ['nein', 'sonstiges'].includes(remoteAeSensorDetected);
  const needsSensorCableInspection = area === 'sensor' && ['nein', 'sporadisch'].includes(remoteAeSensorDetected);

  const anySensorNotDetected = area === 'remote' && [sensorG1Detected, sensorG2Detected, sensorG3Detected].includes('nein');

  const createdAt = new Date().toISOString();
  const windowsUsername = process.env.USERNAME || process.env.USER || 'unknown';
  const microBImageFile = req.files?.microBDamageImage?.[0];
  const usbCImageFile = req.files?.usbCDamageImage?.[0];
  const flashDumpFile = req.files?.flashDumpUpload?.[0];
  const microBImagePath = area === 'remote' && microBImageFile ? `/uploads/${microBImageFile.filename}` : null;
  const usbCImagePath = usbCImageFile ? `/uploads/${usbCImageFile.filename}` : null;
  const flashDumpFilePath = flashDumpFile ? `/uploads/${flashDumpFile.filename}` : null;

  const query = `
    INSERT INTO intake_entries (
      area,
      serial_number,
      hardware_version,
      firmware_on_delivery,
      firmware_version,
      fpga_version,
      oem_version,
      golden_version,
      g1_version,
      g2_version,
      g3_version,
      delivery_date,
      ticket_number,
      ticket_error_description,
      sensor_generation,
      sensor_brand,
      remote_type,
      remote_ae_sensor_detected,
      device_manager_name,
      sensor_cable_inspection,
      sensor_g1_detected,
      sensor_g2_detected,
      sensor_g3_detected,
      sensor_path_fpga_check,
      flashdump_file_path,
      other_checks,
      error_cause,
      current_consumption,
      current_consumption_unit,
      pc_led_state,
      pc_led_state_other,
      board_power_supply_check,
      micro_b_damaged,
      usb_c_damaged,
      micro_b_damage_image,
      usb_c_damage_image,
      created_at,
      windows_username
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `;

  const values = [
    area,
    serialNumber,
    hardwareVersion,
    firmwareOnDelivery,
    firmwareVersion,
    area === 'remote' ? fpgaVersion : null,
    area === 'sensor' ? oemVersion : null,
    area === 'remote' ? goldenVersion : null,
    area === 'remote' ? g1Version : null,
    area === 'remote' ? g2Version : null,
    area === 'remote' ? g3Version : null,
    deliveryDate || '',
    ticketNumber || '',
    ticketErrorDescription || '',
    area === 'sensor' ? sensorGeneration : null,
    area === 'sensor' ? sensorBrand : null,
    area === 'remote' ? remoteType : null,
    remoteAeSensorDetected,
    needsDeviceName ? String(deviceManagerName || '').trim() : null,
    needsSensorCableInspection ? String(sensorCableInspection || '').trim() : null,
    area === 'remote' ? sensorG1Detected : null,
    area === 'remote' ? sensorG2Detected : null,
    area === 'remote' ? sensorG3Detected : null,
    anySensorNotDetected ? String(sensorPathFpgaCheck || '').trim() : null,
    flashDumpFilePath,
    String(otherChecks || '').trim(),
    String(errorCause || '').trim(),
    currentConsumption,
    currentConsumptionUnit,
    pcLedState,
    pcLedState === 'sonstiges' ? String(pcLedStateOther || '').trim() : null,
    pcLedState === 'aus' ? String(boardPowerSupplyCheck || '').trim() : null,
    area === 'remote' ? microBDamaged : null,
    usbCDamaged,
    microBImagePath,
    usbCImagePath,
    createdAt,
    windowsUsername
  ];

  db.run(query, values, function onInsert(err) {
    if (err) {
      return res.status(500).json({ error: 'Fehler beim Speichern in die Datenbank.' });
    }

    return res.status(201).json({
      message: 'Daten erfolgreich gespeichert.',
      id: this.lastID,
      createdAt,
      windowsUsername
    });
  });
});

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.listen(port, host, () => {
  const networkAddresses = Object.values(os.networkInterfaces())
    .flat()
    .filter((address) => address && address.family === 'IPv4' && !address.internal)
    .map((address) => address.address);

  console.log(`Server laeuft unter http://${host}:${port}`);
  if (networkAddresses.length > 0) {
    console.log(`Im Netzwerk erreichbar unter: ${networkAddresses.map((address) => `http://${address}:${port}`).join(', ')}`);
  }
});
