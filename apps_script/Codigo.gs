/**
 * Dashboard Nanni - Sensores ESP
 * - Importa a esta planilla los archivos mensuales consolidados que van
 *   apareciendo en una carpeta de Drive (subidos por GitHub Actions).
 * - Permite agregar manualmente, desde el menú, un día del mes en curso
 *   que todavía no fue consolidado, trayéndolo directo del repo de GitHub.
 *
 * Antes de usar:
 *  1) Completar DRIVE_FOLDER_ID abajo con el ID de la carpeta de Drive.
 *  2) En el editor de Apps Script: Servicios (ícono +) > agregar "Drive API".
 */

const CONFIG = {
  DRIVE_FOLDER_ID: 'PON_AQUI_EL_ID_DE_LA_CARPETA_DE_DRIVE',
  GITHUB_RAW_BASE: 'https://raw.githubusercontent.com/lbechi/esp-sensores/main',
  SHEET_DATOS: 'Datos',
  SHEET_ALERTAS: 'Alertas',
  SHEET_IMPORTADOS: 'Importados',
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Nanni Sensores')
    .addItem('Importar meses nuevos de Drive', 'importarMesesNuevos')
    .addItem('Agregar día del mes actual', 'agregarDiaActualUI')
    .addToUi();
}

// ---------- Utilidades comunes ----------

function getOrCreateSheet(nombre, encabezados) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let hoja = ss.getSheetByName(nombre);
  if (!hoja) {
    hoja = ss.insertSheet(nombre);
    hoja.appendRow(encabezados);
  }
  return hoja;
}

function convertirXlsxATemp(blob, nombre) {
  const recurso = { name: nombre, mimeType: MimeType.GOOGLE_SHEETS };
  const archivo = Drive.Files.create(recurso, blob, { fields: 'id' });
  return archivo.id;
}

function leerFilasDeArchivoTemp(fileId) {
  const ss = SpreadsheetApp.openById(fileId);
  const hoja = ss.getSheets()[0];
  const datos = hoja.getDataRange().getValues();
  DriveApp.getFileById(fileId).setTrashed(true); // borra el temporal
  return datos; // incluye encabezado en la fila 0
}

function borrarFilasPorCondicion(hoja, condicionFn) {
  const datos = hoja.getDataRange().getValues();
  for (let i = datos.length - 1; i >= 1; i--) {
    if (condicionFn(datos[i])) {
      hoja.deleteRow(i + 1);
    }
  }
}

// ---------- Importación mensual desde Drive ----------

function importarMesesNuevos() {
  const carpeta = DriveApp.getFolderById(CONFIG.DRIVE_FOLDER_ID);
  const importados = getOrCreateSheet(CONFIG.SHEET_IMPORTADOS, ['Archivo', 'FechaImportacion']);
  const yaImportados = importados.getDataRange().getValues().slice(1).map(f => f[0]);

  const archivos = carpeta.getFiles();
  while (archivos.hasNext()) {
    const archivo = archivos.next();
    const nombre = archivo.getName();
    if (yaImportados.indexOf(nombre) !== -1) continue;

    const matchDatos = nombre.match(/^sensores_(\d{4})-(\d{2})\.(xlsx|csv)$/);
    const matchAlertas = nombre.match(/^alertas_(\d{4})-(\d{2})\.(xlsx|csv)$/);

    if (matchDatos) {
      procesarArchivoMensual(archivo, matchDatos[1], matchDatos[2], CONFIG.SHEET_DATOS,
        ['Fecha', 'Dispositivo', 'Sensor', 'Valor', 'Unidad', 'Origen']);
    } else if (matchAlertas) {
      procesarArchivoMensual(archivo, matchAlertas[1], matchAlertas[2], CONFIG.SHEET_ALERTAS,
        ['Fecha', 'Nombre', 'Dispositivo', 'Sensor', 'Valor', 'Unidad', 'Origen']);
    } else {
      continue;
    }

    importados.appendRow([nombre, new Date()]);
  }

  SpreadsheetApp.getUi().alert('Importación de meses completada.');
}

function procesarArchivoMensual(archivo, anio, mes, nombreHoja, encabezados) {
  const hoja = getOrCreateSheet(nombreHoja, encabezados);

  // Saca del buffer manual las filas de ese mes, para no duplicar
  // lo que ya se había agregado a mano con "Agregar día del mes actual"
  const anioMes = anio + '-' + mes;
  borrarFilasPorCondicion(hoja, fila => {
    const origen = fila[fila.length - 1];
    const fecha = fila[0];
    return origen === 'diario_manual' && String(fecha).indexOf(anioMes) === 0;
  });

  const tempId = convertirXlsxATemp(archivo.getBlob(), 'temp_' + archivo.getName());
  const filas = leerFilasDeArchivoTemp(tempId);

  for (let i = 1; i < filas.length; i++) { // saltea encabezado
    hoja.appendRow(filas[i].concat(['mensual']));
  }
}

// ---------- Agregar día no consolidado del mes en curso ----------

function agregarDiaActualUI() {
  const ui = SpreadsheetApp.getUi();
  const respuesta = ui.prompt('Agregar día del mes en curso',
    'Ingresá la fecha (YYYY-MM-DD):', ui.ButtonSet.OK_CANCEL);

  if (respuesta.getSelectedButton() !== ui.Button.OK) return;
  const fecha = respuesta.getResponseText().trim();

  try {
    agregarDia(fecha);
    ui.alert('Día ' + fecha + ' agregado correctamente.');
  } catch (e) {
    ui.alert('Error al agregar el día: ' + e.message);
  }
}

function agregarDia(fecha) {
  agregarDiaDeCategoria(fecha, 'datos', 'sensores', CONFIG.SHEET_DATOS,
    ['Fecha', 'Dispositivo', 'Sensor', 'Valor', 'Unidad', 'Origen']);
  agregarDiaDeCategoria(fecha, 'alertas', 'alertas', CONFIG.SHEET_ALERTAS,
    ['Fecha', 'Nombre', 'Dispositivo', 'Sensor', 'Valor', 'Unidad', 'Origen']);
}

function agregarDiaDeCategoria(fecha, carpetaGithub, prefijo, nombreHoja, encabezados) {
  const url = CONFIG.GITHUB_RAW_BASE + '/' + carpetaGithub + '/' + prefijo + '_' + fecha + '.xlsx';
  const respuesta = UrlFetchApp.fetch(url, { muteHttpExceptions: true });

  if (respuesta.getResponseCode() !== 200) {
    throw new Error('No se encontró el archivo ' + prefijo + '_' + fecha + '.xlsx en el repo');
  }

  const hoja = getOrCreateSheet(nombreHoja, encabezados);

  // Evita duplicar si ya se había agregado este día a mano antes
  borrarFilasPorCondicion(hoja, fila => {
    const origen = fila[fila.length - 1];
    return origen === 'diario_manual' && String(fila[0]).indexOf(fecha) === 0;
  });

  const tempId = convertirXlsxATemp(respuesta.getBlob(), 'temp_' + prefijo + '_' + fecha);
  const filas = leerFilasDeArchivoTemp(tempId);

  for (let i = 1; i < filas.length; i++) {
    hoja.appendRow(filas[i].concat(['diario_manual']));
  }
}
