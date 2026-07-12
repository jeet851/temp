// Helper: Recursively convert snake_case keys to camelCase
export function toCamel(o: any): any {
  if (o === null || o === undefined) return o;
  if (Array.isArray(o)) {
    return o.map(toCamel);
  }
  if (typeof o === 'object' && o.constructor === Object) {
    const n: Record<string, any> = {};
    Object.keys(o).forEach((k) => {
      const ck = k.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
      n[ck] = toCamel(o[k]);
    });
    return n;
  }
  return o;
}

// Helper: Recursively convert camelCase keys to snake_case
export function toSnake(o: any): any {
  if (o === null || o === undefined) return o;
  if (Array.isArray(o)) {
    return o.map(toSnake);
  }
  if (typeof o === 'object' && o.constructor === Object) {
    const n: Record<string, any> = {};
    Object.keys(o).forEach((k) => {
      const sk = k.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
      n[sk] = toSnake(o[k]);
    });
    return n;
  }
  return o;
}
