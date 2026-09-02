const form = document.getElementById('intakeForm');
const resultMessage = document.getElementById('resultMessage');
const sensorTab = document.getElementById('sensorTab');
const remoteTab = document.getElementById('remoteTab');
const remoteFields = document.getElementById('remoteFields');
const remoteTypeInIntake = document.getElementById('remoteTypeInIntake');
const sensorTypeInIntake = document.getElementById('sensorTypeInIntake');
const sensorBrandInIntake = document.getElementById('sensorBrandInIntake');
const fpgaVersionField = document.getElementById('fpgaVersionField');
const oemVersionField = document.getElementById('oemVersionField');
const goldenVersionField = document.getElementById('goldenVersionField');
const g1VersionField = document.getElementById('g1VersionField');
const g2VersionField = document.getElementById('g2VersionField');
const g3VersionField = document.getElementById('g3VersionField');
const microBDamageField = document.getElementById('microBDamageField');
const serialInput = form.serialNumber;
const microBExistingImage = document.getElementById('microBExistingImage');
const usbCExistingImage = document.getElementById('usbCExistingImage');
const usbCDamageQuestionText = document.getElementById('usbCDamageQuestionText');
const usbCDamageUploadText = document.getElementById('usbCDamageUploadText');
const analysisPowerTitle = document.getElementById('analysisPowerTitle');
const analysisPowerSubtitle = document.getElementById('analysisPowerSubtitle');
const ledStateLabelText = document.getElementById('ledStateLabelText');
const ledOtherLabelText = document.getElementById('ledOtherLabelText');
const boardPowerSupplyTitleText = document.getElementById('boardPowerSupplyTitleText');
const boardPowerSupplyNoteText = document.getElementById('boardPowerSupplyNoteText');
const boardPowerSupplyCheckInput = form.boardPowerSupplyCheck;
const detectionTitle = document.getElementById('detectionTitle');
const remoteDetectionQuestionText = document.getElementById('remoteDetectionQuestionText');
const remoteDetectionThirdOption = document.getElementById('remoteDetectionThirdOption');
const sensorDetectionSubtitle = document.getElementById('sensorDetectionSubtitle');
const sensorCableInspectionWrapper = document.getElementById('sensorCableInspectionWrapper');
const sensorG1DetectedWrapper = form.sensorG1Detected.closest('label');
const sensorG2DetectedWrapper = form.sensorG2Detected.closest('label');
const sensorG3DetectedWrapper = form.sensorG3Detected.closest('label');
const pcLedState = document.getElementById('pcLedState');
const pcLedOtherWrapper = document.getElementById('pcLedOtherWrapper');
const boardPowerSupplyCheckWrapper = document.getElementById('boardPowerSupplyCheckWrapper');
const remoteAeSensorDetected = document.getElementById('remoteAeSensorDetected');
const deviceManagerNameWrapper = document.getElementById('deviceManagerNameWrapper');
const sensorPathCheckWrapper = document.getElementById('sensorPathCheckWrapper');
const flashDumpExistingFile = document.getElementById('flashDumpExistingFile');
const rootCauseUploadText = document.getElementById('rootCauseUploadText');
const rootCauseExistingFile = document.getElementById('rootCauseExistingFile');

let activeArea = 'remote';
let lookupTimeoutId = null;
let serialLookupRequestId = 0;

function clearLoadedFields(preserveSerial = true) {
  const serialValue = preserveSerial ? form.serialNumber.value : '';

  form.ticketNumber.value = '';
  form.deliveryDate.value = '';
  form.hardwareVersion.value = '';
  form.firmwareVersion.value = '';
  form.ticketErrorDescription.value = '';
  form.sensorGeneration.value = '';
  form.sensorBrand.value = '';
  form.remoteType.value = '';
  form.fpgaVersion.value = '';
  form.oemVersion.value = '';
  form.goldenVersion.value = '';
  form.g1Version.value = '';
  form.g2Version.value = '';
  form.g3Version.value = '';
  form.microBDamaged.value = '';
  form.usbCDamaged.value = '';
  form.currentConsumption.value = '';
  form.currentConsumptionUnit.value = '';
  form.pcLedState.value = '';
  form.pcLedStateOther.value = '';
  form.boardPowerSupplyCheck.value = '';
  form.remoteAeSensorDetected.value = '';
  form.deviceManagerName.value = '';
  form.sensorCableInspection.value = '';
  form.sensorG1Detected.value = '';
  form.sensorG2Detected.value = '';
  form.sensorG3Detected.value = '';
  form.sensorPathFpgaCheck.value = '';
  form.otherChecks.value = '';
  form.errorCause.value = '';
  form.rootCauseUpload.value = '';

  updateExistingImageLink(microBExistingImage, '');
  updateExistingImageLink(usbCExistingImage, '');
  updateExistingImageLink(flashDumpExistingFile, '');
  updateExistingImageLink(rootCauseExistingFile, '');

  form.serialNumber.value = serialValue;
  updatePcLedOtherVisibility();
  updateDeviceManagerNameVisibility();
  updateSensorCableInspectionVisibility();
  updateSensorPathCheckVisibility();
}

function updateDeviceManagerNameVisibility() {
  const needsDeviceName = activeArea === 'remote' && ['nein', 'sonstiges'].includes(form.remoteAeSensorDetected.value);
  deviceManagerNameWrapper.classList.toggle('hidden', !needsDeviceName);
}

function updateSensorCableInspectionVisibility() {
  const needsInspection = activeArea === 'sensor' && ['nein', 'sporadisch'].includes(form.remoteAeSensorDetected.value);
  sensorCableInspectionWrapper.classList.toggle('hidden', !needsInspection);
}

function updatePcLedOtherVisibility() {
  const showOther = form.pcLedState.value === 'sonstiges';
  pcLedOtherWrapper.classList.toggle('hidden', !showOther);
}

function updateSensorPathCheckVisibility() {
  if (activeArea === 'sensor') {
    sensorPathCheckWrapper.classList.add('hidden');
    flashDumpExistingFile.classList.add('hidden');
    flashDumpExistingFile.removeAttribute('href');
    return;
  }

  const anySensorNotDetected =
    [form.sensorG1Detected.value, form.sensorG2Detected.value, form.sensorG3Detected.value].includes('nein');

  sensorPathCheckWrapper.classList.toggle('hidden', !anySensorNotDetected);
}

function setArea(area) {
  activeArea = area;

  const isSensor = area === 'sensor';

  sensorTab.classList.toggle('active', isSensor);
  remoteTab.classList.toggle('active', !isSensor);

  sensorTab.setAttribute('aria-selected', String(isSensor));
  remoteTab.setAttribute('aria-selected', String(!isSensor));

  remoteFields.classList.remove('hidden');
  remoteTypeInIntake.classList.toggle('hidden', isSensor);
  sensorTypeInIntake.classList.toggle('hidden', !isSensor);
  sensorBrandInIntake.classList.toggle('hidden', !isSensor);
  fpgaVersionField.classList.toggle('hidden', isSensor);
  oemVersionField.classList.toggle('hidden', !isSensor);
  goldenVersionField.classList.toggle('hidden', isSensor);
  g1VersionField.classList.toggle('hidden', isSensor);
  g2VersionField.classList.toggle('hidden', isSensor);
  g3VersionField.classList.toggle('hidden', isSensor);
  microBDamageField.classList.toggle('hidden', isSensor);
  sensorG1DetectedWrapper.classList.toggle('hidden', isSensor);
  sensorG2DetectedWrapper.classList.toggle('hidden', isSensor);
  sensorG3DetectedWrapper.classList.toggle('hidden', isSensor);

  if (isSensor) {
    usbCDamageQuestionText.textContent = 'Ist der USB-C-Stecker beschaedigt?';
    usbCDamageUploadText.textContent = 'Bild zum USB-C-Stecker (optional)';
    analysisPowerTitle.textContent = 'Sensor an funktionierende Remote anschliessen';
    analysisPowerSubtitle.textContent = '';
    analysisPowerSubtitle.classList.add('hidden');
    ledStateLabelText.textContent = 'Sensor LED-Zustand';
    ledOtherLabelText.textContent = 'Beschreibung der Sensor LED-Zustand';
    boardPowerSupplyTitleText.textContent = 'Beschreibung des Sensor LED-Zustand';
    boardPowerSupplyNoteText.textContent = '';
    boardPowerSupplyNoteText.classList.add('hidden');
    boardPowerSupplyCheckInput.placeholder = 'Bitte Beschreibung des Sensor LED-Zustand eingeben';
    detectionTitle.textContent = 'Sensor-Erkennung';
    remoteDetectionQuestionText.textContent = 'Sensor wird permanent von der Remote erkannt';
    remoteDetectionThirdOption.value = 'sporadisch';
    remoteDetectionThirdOption.textContent = 'sporadisch';
    sensorDetectionSubtitle.textContent = 'Die unterschiedlichen Sensoren (G1, G2, G3) werden erkannt (nach Anstecken des Sensors leuchtet die Sensor-LED permanent gruen).';
    deviceManagerNameWrapper.classList.add('hidden');
    form.deviceManagerName.required = false;
    sensorCableInspectionWrapper.classList.add('hidden');
    form.sensorCableInspection.required = false;
    sensorDetectionSubtitle.classList.add('hidden');
    flashDumpExistingFile.classList.add('hidden');
    flashDumpExistingFile.removeAttribute('href');
    rootCauseUploadText.textContent = 'RootCause-Datei Sensor (optional)';
  } else {
    usbCDamageQuestionText.textContent = 'Ist die USB-C Buchse beschaedigt?';
    usbCDamageUploadText.textContent = 'Bild zur USB-C Buchse (optional)';
    analysisPowerTitle.textContent = 'Remote mit Energie versorgen';
    analysisPowerSubtitle.textContent = 'Hinweis: Es soll bei diesem Test kein Sensor angesteckt sein.';
    analysisPowerSubtitle.classList.remove('hidden');
    ledStateLabelText.textContent = 'PC LED-Zustand';
    ledOtherLabelText.textContent = 'LED-Verhalten (bei sonstiges)';
    boardPowerSupplyTitleText.textContent = 'Spannungsversorgung auf der Platine pruefen';
    boardPowerSupplyNoteText.textContent = 'Optional. Wird nur bei PC LED-Zustand "aus" zum Pflichtfeld.';
    boardPowerSupplyNoteText.classList.remove('hidden');
    boardPowerSupplyCheckInput.placeholder = 'Bitte Pruefergebnis der Spannungsversorgung eingeben';
    detectionTitle.textContent = 'Sensor/Remote-Erkennung';
    remoteDetectionQuestionText.textContent = 'Remote wird vom PC permanent als AE Sensor USB Interface erkannt';
    remoteDetectionThirdOption.value = 'sonstiges';
    remoteDetectionThirdOption.textContent = 'Sonstiges';
    sensorDetectionSubtitle.textContent = 'Die unterschiedlichen Sensoren (G1, G2, G3) werden von der Remote erkannt (nach Anstecken des Sensors leuchtet die Sensor-LED permanent gruen).';
    sensorDetectionSubtitle.classList.remove('hidden');
    rootCauseUploadText.textContent = 'RootCause-Datei Remote (optional)';
  }

  if (isSensor) {
    form.remoteType.value = '';
    form.fpgaVersion.value = '';
    form.goldenVersion.value = '';
    form.g1Version.value = '';
    form.g2Version.value = '';
    form.g3Version.value = '';
    form.microBDamaged.value = '';
    form.microBDamageImage.value = '';
    microBExistingImage.classList.add('hidden');
    microBExistingImage.removeAttribute('href');
  } else {
    form.sensorGeneration.value = '';
    form.sensorBrand.value = '';
    form.oemVersion.value = '';
  }

  resultMessage.textContent = '';
  resultMessage.className = 'message';
  updatePcLedOtherVisibility();
  updateDeviceManagerNameVisibility();
  updateSensorCableInspectionVisibility();
  updateSensorPathCheckVisibility();
}

function updateExistingImageLink(linkElement, imagePath) {
  if (!imagePath) {
    linkElement.classList.add('hidden');
    linkElement.removeAttribute('href');
    return;
  }

  linkElement.href = imagePath;
  linkElement.classList.remove('hidden');
}

sensorTab.addEventListener('click', () => {
  setArea('sensor');
  if (serialInput.value.trim()) {
    clearTimeout(lookupTimeoutId);
    fillBySerialNumber();
  }
});

remoteTab.addEventListener('click', () => {
  setArea('remote');
  if (serialInput.value.trim()) {
    clearTimeout(lookupTimeoutId);
    fillBySerialNumber();
  }
});
pcLedState.addEventListener('change', updatePcLedOtherVisibility);
remoteAeSensorDetected.addEventListener('change', updateDeviceManagerNameVisibility);
remoteAeSensorDetected.addEventListener('change', updateSensorCableInspectionVisibility);
form.sensorG1Detected.addEventListener('change', updateSensorPathCheckVisibility);
form.sensorG2Detected.addEventListener('change', updateSensorPathCheckVisibility);
form.sensorG3Detected.addEventListener('change', updateSensorPathCheckVisibility);

async function fillBySerialNumber() {
  const serialNumber = serialInput.value.trim();
  const requestId = ++serialLookupRequestId;
  const requestedArea = activeArea;

  if (!serialNumber) {
    return;
  }

  try {
    const response = await fetch(`/api/intake/by-serial/${encodeURIComponent(serialNumber)}?area=${encodeURIComponent(requestedArea)}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Fehler beim Laden vorhandener Daten.');
    }

    // Ignore stale responses from older requests.
    if (requestId !== serialLookupRequestId || serialInput.value.trim() !== serialNumber || activeArea !== requestedArea) {
      return;
    }

    if (!data.found || !data.entry) {
      clearLoadedFields(true);
      resultMessage.textContent = `Kein Datensatz fuer Bereich ${requestedArea === 'sensor' ? 'Sensor' : 'Remote'} gefunden.`;
      resultMessage.className = 'message';
      return;
    }

    const entry = data.entry;

    form.serialNumber.value = entry.serial_number || serialNumber;
    form.hardwareVersion.value = entry.hardware_version || '';
    form.firmwareVersion.value = entry.firmware_version || '';
    form.deliveryDate.value = entry.delivery_date || '';
    form.ticketNumber.value = entry.ticket_number || '';
    form.ticketErrorDescription.value = entry.ticket_error_description || '';
    form.usbCDamaged.value = entry.usb_c_damaged || '';
    form.currentConsumption.value = entry.current_consumption || '';
    form.currentConsumptionUnit.value = entry.current_consumption_unit || '';
    form.pcLedState.value = entry.pc_led_state || '';
    form.pcLedStateOther.value = entry.pc_led_state_other || '';
    form.boardPowerSupplyCheck.value = entry.board_power_supply_check || '';
    form.remoteAeSensorDetected.value = entry.remote_ae_sensor_detected || '';
    form.otherChecks.value = entry.other_checks || '';
    form.errorCause.value = entry.error_cause || '';

    if (requestedArea === 'remote') {
      form.fpgaVersion.value = entry.fpga_version || '';
      form.goldenVersion.value = entry.golden_version || '';
      form.g1Version.value = entry.g1_version || '';
      form.g2Version.value = entry.g2_version || '';
      form.g3Version.value = entry.g3_version || '';
      form.remoteType.value = entry.remote_type || '';
      form.microBDamaged.value = entry.micro_b_damaged || '';
      form.deviceManagerName.value = entry.device_manager_name || '';
      form.sensorG1Detected.value = entry.sensor_g1_detected || '';
      form.sensorG2Detected.value = entry.sensor_g2_detected || '';
      form.sensorG3Detected.value = entry.sensor_g3_detected || '';
      form.sensorPathFpgaCheck.value = entry.sensor_path_fpga_check || '';

      form.oemVersion.value = '';
      form.sensorGeneration.value = '';
      form.sensorBrand.value = '';
      form.sensorCableInspection.value = '';
      updateExistingImageLink(microBExistingImage, entry.micro_b_damage_image || '');
    } else {
      form.oemVersion.value = entry.oem_version || '';
      form.sensorGeneration.value = entry.sensor_generation || '';
      form.sensorBrand.value = entry.sensor_brand || '';
      form.sensorCableInspection.value = entry.sensor_cable_inspection || '';

      form.fpgaVersion.value = '';
      form.goldenVersion.value = '';
      form.g1Version.value = '';
      form.g2Version.value = '';
      form.g3Version.value = '';
      form.remoteType.value = '';
      form.microBDamaged.value = '';
      form.deviceManagerName.value = '';
      form.sensorG1Detected.value = '';
      form.sensorG2Detected.value = '';
      form.sensorG3Detected.value = '';
      form.sensorPathFpgaCheck.value = '';
      updateExistingImageLink(microBExistingImage, '');
    }

    updateExistingImageLink(usbCExistingImage, entry.usb_c_damage_image || '');
    updateExistingImageLink(flashDumpExistingFile, entry.flashdump_file_path || '');
    updateExistingImageLink(rootCauseExistingFile, entry.root_cause_file_path || '');
    updatePcLedOtherVisibility();
    updateDeviceManagerNameVisibility();
    updateSensorCableInspectionVisibility();
    updateSensorPathCheckVisibility();

    resultMessage.textContent = 'Vorhandener Datensatz zur Seriennummer gefunden. Felder wurden gefuellt.';
    resultMessage.className = 'message success';
  } catch (error) {
    if (requestId !== serialLookupRequestId || serialInput.value.trim() !== serialNumber || activeArea !== requestedArea) {
      return;
    }

    resultMessage.textContent = error.message;
    resultMessage.className = 'message error';
  }
}

serialInput.addEventListener('input', () => {
  clearTimeout(lookupTimeoutId);
  lookupTimeoutId = setTimeout(fillBySerialNumber, 450);
});

serialInput.addEventListener('blur', () => {
  clearTimeout(lookupTimeoutId);
  fillBySerialNumber();
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const formData = new FormData();
  formData.append('area', activeArea);
  formData.append('serialNumber', form.serialNumber.value.trim());
  formData.append('hardwareVersion', form.hardwareVersion.value.trim());
  formData.append('firmwareVersion', form.firmwareVersion.value.trim());
  formData.append('fpgaVersion', form.fpgaVersion.value.trim());
  formData.append('oemVersion', form.oemVersion.value.trim());
  formData.append('goldenVersion', form.goldenVersion.value.trim());
  formData.append('g1Version', form.g1Version.value.trim());
  formData.append('g2Version', form.g2Version.value.trim());
  formData.append('g3Version', form.g3Version.value.trim());
  formData.append('deliveryDate', form.deliveryDate.value);
  formData.append('ticketNumber', form.ticketNumber.value.trim());
  formData.append('ticketErrorDescription', form.ticketErrorDescription.value.trim());
  formData.append('sensorGeneration', form.sensorGeneration.value.trim());
  formData.append('sensorBrand', form.sensorBrand.value.trim());
  formData.append('remoteType', form.remoteType.value);
  formData.append('microBDamaged', form.microBDamaged.value);
  formData.append('usbCDamaged', form.usbCDamaged.value);
  formData.append('currentConsumption', form.currentConsumption.value.trim());
  formData.append('currentConsumptionUnit', form.currentConsumptionUnit.value);
  formData.append('pcLedState', form.pcLedState.value);
  formData.append('pcLedStateOther', form.pcLedStateOther.value.trim());
  formData.append('boardPowerSupplyCheck', form.boardPowerSupplyCheck.value.trim());
  formData.append('remoteAeSensorDetected', form.remoteAeSensorDetected.value);
  formData.append('deviceManagerName', form.deviceManagerName.value.trim());
  formData.append('sensorCableInspection', form.sensorCableInspection.value.trim());
  formData.append('sensorG1Detected', activeArea === 'remote' ? form.sensorG1Detected.value : '');
  formData.append('sensorG2Detected', activeArea === 'remote' ? form.sensorG2Detected.value : '');
  formData.append('sensorG3Detected', activeArea === 'remote' ? form.sensorG3Detected.value : '');
  formData.append('sensorPathFpgaCheck', form.sensorPathFpgaCheck.value.trim());
  formData.append('otherChecks', form.otherChecks.value.trim());
  formData.append('errorCause', form.errorCause.value.trim());

  if (form.microBDamageImage.files[0]) {
    formData.append('microBDamageImage', form.microBDamageImage.files[0]);
  }

  if (form.usbCDamageImage.files[0]) {
    formData.append('usbCDamageImage', form.usbCDamageImage.files[0]);
  }

  if (form.flashDumpUpload.files[0]) {
    formData.append('flashDumpUpload', form.flashDumpUpload.files[0]);
  }

  if (form.rootCauseUpload.files[0]) {
    formData.append('rootCauseUpload', form.rootCauseUpload.files[0]);
  }

  try {
    const response = await fetch('/api/intake', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Unbekannter Fehler.');
    }

    resultMessage.textContent = `Gespeichert. ID: ${data.id}, Zeitstempel: ${data.createdAt}, User: ${data.windowsUsername}`;
    resultMessage.className = 'message success';
  } catch (error) {
    resultMessage.textContent = error.message;
    resultMessage.className = 'message error';
  }
});

setArea('remote');
