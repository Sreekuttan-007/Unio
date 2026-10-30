/** A picked file as the base64 data URL the upload endpoints accept. */
export function readAsUpload(file: File): Promise<{ name: string; mime: string; contentBase64: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve({ name: file.name.slice(0, 120), mime: file.type || 'application/octet-stream', contentBase64: String(reader.result) })
    reader.onerror = () => reject(reader.error ?? new Error('That file could not be read.'))
    reader.readAsDataURL(file)
  })
}
