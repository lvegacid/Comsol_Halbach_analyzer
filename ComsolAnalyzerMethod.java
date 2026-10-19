// =============================================================================
// COMSOL Analyzer - Method del Application Builder (Java)
//
// Traduccion de comsol_analyzer_gui.m + extraction_controller.m + export_*.m.
// Pegar TODO este contenido como cuerpo de un Method (p.ej. "ComsolAnalyzer")
// y ejecutarlo desde un boton / Test Application. Usa el objeto global "model".
//
// - Sin "import": todo va con nombres completos (el editor de Methods no
//   admite imports). Las funciones auxiliares son clases locales.
// - Dialogos: javax.swing.JOptionPane con paneles Swing como contenido.
// - Si COMSOL bloquea javax.swing / java.io / ProcessBuilder, revisa
//   Preferences > Security (permisos de Methods y acceso a ficheros).
//   Si se bloquea el lanzamiento de Python, el postproceso se omite y los
//   comandos se guardan en run_python_postprocess.bat dentro de la carpeta de salida.
// - Solo sintaxis Java 8.
// =============================================================================

final String DEFAULT_SCRIPT_DIR = "Z:\\Projects\\Magnets\\Scripts\\Comsol_analyzer";

// ----------------------------------------------------------------------------
// Datos
// ----------------------------------------------------------------------------
class Sel {
    String tag; String label;
    Sel(String t, String l) { tag = t; label = l; }
    public String toString() { return label + "   [" + tag + "]"; }
}

// Valores de un Parametric Sweep: cada combinacion corresponde a una "outer solution" (mismo orden)
class SweepInfo {
    String study = ""; String solTag = ""; boolean viaParent = false; boolean hasUnits = false;
    String[] names = new String[0];
    java.util.List<double[]> combos = new java.util.ArrayList<double[]>();
    java.util.List<String> labels = new java.util.ArrayList<String>();   // "mu_trans = 1.05"
    java.util.List<String> suffixes = new java.util.ArrayList<String>(); // "mu_trans_1.05"

    int count() { return combos.size(); }
}

class Ds {
    String tag; String label; String shortLabel;
    // Parametric Sweep: valor del barrido tratado como estudio independiente (sweepIdx 1-based, 0 = sin barrido)
    String srcTag = ""; int sweepIdx = 0; String folderName = ""; SweepInfo sweep = null;
    public String toString() { return tag + ": " + label; }
}

class ExtraH {
    String name; double value;
}

class CoordCfg {
    boolean fromFile = false;
    int nTheta = 100; int nPhi = 100; double R = 0.1;
    String filePath = ""; int[] cols = new int[] {1, 2, 3};
    double[][] coords;
    String outputBaseName = "";
}

class MagCfg {
    int bins = 100; double step = 2; double br = 1.4;
    boolean normM = true; boolean normH = false;
    double hcb = Double.NaN; double hcj = Double.NaN;
    double hknee = Double.NaN; double hlinearEnd = Double.NaN;
    java.util.List<ExtraH> extra = new java.util.ArrayList<ExtraH>();
}

class Opts {
    String outDir = ""; String modelName = ""; String fovInfo = "";
    String scriptDir = ""; boolean runPython = true; String field = "By";
    boolean bfov3d = true; boolean bfovHist = true; boolean bfovCoord = false;
    boolean changeFov = false; boolean magnets3d = false; boolean magnetsHist = false;
    boolean changeOrtho = false;
    boolean domainMode = false; java.util.List<Sel> domains = new java.util.ArrayList<Sel>();
    int histBins = 100; double orthoScale = 0.35;
    CoordCfg coord = new CoordCfg(); MagCfg mag = new MagCfg();
}

// ----------------------------------------------------------------------------
// Preferencias persistentes (equivalente a getpref/setpref)
// ----------------------------------------------------------------------------
class Prefs {
    java.util.prefs.Preferences p;
    Prefs() {
        try { p = java.util.prefs.Preferences.userRoot().node("ComsolAnalyzer"); }
        catch (Throwable t) { p = null; }
    }
    String s(String k, String d) { try { return p == null ? d : p.get(k, d); } catch (Throwable t) { return d; } }
    double d(String k, double d) { try { return p == null ? d : p.getDouble(k, d); } catch (Throwable t) { return d; } }
    void put(String k, String v) { try { if (p != null) p.put(k, v); } catch (Throwable t) { } }
    void put(String k, double v) { try { if (p != null) p.putDouble(k, v); } catch (Throwable t) { } }
}

// ----------------------------------------------------------------------------
// Log: consola + resumen final
// ----------------------------------------------------------------------------
class Log {
    StringBuilder sb = new StringBuilder();
    void log(String level, String tag, String msg) {
        String ts = new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss").format(new java.util.Date());
        String line = "[" + ts + "] " + level + (tag == null || tag.isEmpty() ? "" : " (" + tag + ")") + ": " + msg;
        sb.append(line).append("\n");
        System.out.println(line);
    }
}

// ----------------------------------------------------------------------------
// Utilidades (equivalentes a make_safe_name, create_output_folder, etc.)
// ----------------------------------------------------------------------------
class Util {
    String safeName(String s) {
        if (s == null || s.isEmpty()) return "";
        return s.replaceAll("[^a-zA-Z0-9_]", "_").replaceAll("[. ]+$", "");
    }

    String mmToken(double rMm) {
        if (Math.abs(rMm - Math.round(rMm)) < 1e-9) return String.valueOf(Math.round(rMm));
        String t = String.format(java.util.Locale.ROOT, "%.6f", rMm);
        t = t.replaceAll("0+$", "").replaceAll("\\.$", "");
        return t.replace('.', 'p');
    }

    Double num(String s) {
        if (s == null) return null;
        try {
            double v = Double.parseDouble(s.trim().replace(',', '.'));
            if (Double.isNaN(v) || Double.isInfinite(v)) return null;
            return Double.valueOf(v);
        } catch (Exception e) { return null; }
    }

    Integer integer(String s) {
        Double v = num(s);
        if (v == null || v.doubleValue() != Math.floor(v.doubleValue())) return null;
        return Integer.valueOf((int) v.doubleValue());
    }

    String fmt(double v) { return String.valueOf(v); }

    // Valor numerico compacto para nombres y etiquetas (1.05, 0.5, 100)
    String numTok(double v) {
        if (v == 0) return "0";
        try { return java.math.BigDecimal.valueOf(v).round(new java.math.MathContext(8)).stripTrailingZeros().toPlainString(); }
        catch (Throwable t) { return String.valueOf(v); }
    }

    // Como safeName pero conserva '.' y '-' (para valores de parametros en nombres de carpeta)
    String fsName(String s) {
        if (s == null || s.isEmpty()) return "";
        return s.replaceAll("[^a-zA-Z0-9_.\\-]", "_").replaceAll("[. ]+$", "");
    }

    // Carpeta del .mph actual ("" si el modelo no se ha guardado en disco)
    String modelDir() {
        try {
            String p = str(call(model, "getFilePath"));
            if (p.isEmpty()) return "";
            java.io.File d = new java.io.File(p).getAbsoluteFile().getParentFile();
            return d != null && d.isDirectory() ? d.getPath() : "";
        } catch (Throwable t) { return ""; }
    }

    // Llamada por reflexion a metodos de la API de COMSOL cuya firma no esta garantizada; null si falla
    String lastErr = "";

    Object call(Object target, String name, Object... args) {
        lastErr = "";
        if (target == null) { lastErr = "objeto nulo"; return null; }
        lastErr = "metodo no encontrado: " + name;
        java.lang.reflect.Method[] ms = target.getClass().getMethods();
        for (int i = 0; i < ms.length; i++) {
            if (!ms[i].getName().equals(name) || ms[i].getParameterTypes().length != args.length) continue;
            try { ms[i].setAccessible(true); } catch (Throwable t) { }
            try {
                Object r = ms[i].invoke(target, args);
                lastErr = "";
                return r;
            } catch (Throwable t) {
                Throwable c = t instanceof java.lang.reflect.InvocationTargetException && t.getCause() != null ? t.getCause() : t;
                lastErr = String.valueOf(c.getMessage());
            }
        }
        return null;
    }

    String str(Object o) { return o == null ? "" : String.valueOf(o).trim(); }

    String[] strArr(Object o) {
        if (o instanceof String[]) return (String[]) o;
        return null;
    }

    void flatten(Object o, java.util.List<Double> out) {
        if (o instanceof double[]) {
            double[] a = (double[]) o;
            for (int i = 0; i < a.length; i++) out.add(Double.valueOf(a[i]));
        } else if (o instanceof Object[]) {
            Object[] a = (Object[]) o;
            for (int i = 0; i < a.length; i++) flatten(a[i], out);
        } else if (o instanceof Number) {
            out.add(Double.valueOf(((Number) o).doubleValue()));
        }
    }

    boolean has(String[] arr, String t) {
        if (arr == null) return false;
        for (int i = 0; i < arr.length; i++) if (arr[i].equals(t)) return true;
        return false;
    }

    String typeOf(Object o) {
        try { return String.valueOf(o.getClass().getMethod("getType").invoke(o)); }
        catch (Throwable t) { return ""; }
    }

    java.util.List<Sel> selections() {
        java.util.List<Sel> out = new java.util.ArrayList<Sel>();
        String[] tags = new String[0];
        try { tags = model.component("comp1").selection().tags(); } catch (Throwable t) { }
        for (int i = 0; i < tags.length; i++) {
            String lbl = "";
            try { lbl = model.component("comp1").selection(tags[i]).label().trim(); } catch (Throwable t) { }
            out.add(new Sel(tags[i], lbl.isEmpty() ? tags[i] : lbl));
        }
        return out;
    }

    boolean selectionExists(String tag) {
        java.util.List<Sel> l = selections();
        for (int i = 0; i < l.size(); i++) if (l.get(i).tag.equals(tag)) return true;
        return false;
    }

    // Prioriza selections de tipo Explicit con el label exacto
    String findSelectionByLabel(String label) {
        String found = "";
        String[] tags = new String[0];
        try { tags = model.component("comp1").selection().tags(); } catch (Throwable t) { }
        for (int i = 0; i < tags.length; i++) {
            String lbl = "";
            try { lbl = model.component("comp1").selection(tags[i]).label().trim(); } catch (Throwable t) { }
            if (!lbl.equalsIgnoreCase(label)) continue;
            String typ = typeOf(model.component("comp1").selection(tags[i])).trim();
            if (typ.isEmpty() || typ.equalsIgnoreCase("Explicit") || typ.equalsIgnoreCase("null")) return tags[i];
            if (found.isEmpty()) found = tags[i];
        }
        return found;
    }

    String listSelections() {
        StringBuilder sb = new StringBuilder();
        java.util.List<Sel> l = selections();
        for (int i = 0; i < l.size(); i++) {
            if (i > 0) sb.append(", ");
            sb.append(l.get(i).tag).append("(").append(l.get(i).label).append(")");
        }
        return sb.length() == 0 ? "(ninguna encontrada)" : sb.toString();
    }

    java.util.List<Ds> datasets() {
        java.util.List<Ds> out = new java.util.ArrayList<Ds>();
        String[] tags = model.result().dataset().tags();
        for (int i = 0; i < tags.length; i++) {
            Ds d = new Ds();
            d.tag = tags[i];
            d.label = model.result().dataset(tags[i]).label();
            int k = d.label.indexOf('/');
            d.shortLabel = (k >= 0 ? d.label.substring(0, k) : d.label).trim();
            out.add(d);
        }
        return out;
    }

    boolean datasetExists(String tag) {
        try { return has(model.result().dataset().tags(), tag); } catch (Throwable t) { return false; }
    }

    void ensureParent(String path) throws Exception {
        java.io.File p = new java.io.File(path).getAbsoluteFile().getParentFile();
        if (p != null && !p.exists() && !p.mkdirs()) throw new Exception("No se pudo crear directorio: " + p);
    }

    java.io.File tempFile(String ext, String tag) throws Exception {
        return java.io.File.createTempFile("comsol_" + tag.replaceAll("[^a-zA-Z0-9_]", "_") + "_", "." + ext);
    }

    void move(String src, String dst) throws Exception {
        if (!new java.io.File(src).exists()) throw new Exception("El archivo temporal no existe: " + src);
        ensureParent(dst);
        java.nio.file.Files.move(java.nio.file.Paths.get(src), java.nio.file.Paths.get(dst),
            java.nio.file.StandardCopyOption.REPLACE_EXISTING);
    }

    void deleteQuiet(String path) {
        try { if (path != null && !path.isEmpty()) new java.io.File(path).delete(); } catch (Throwable t) { }
    }

    void deleteTree(java.io.File f) {
        try {
            java.io.File[] kids = f.listFiles();
            if (kids != null) for (int i = 0; i < kids.length; i++) deleteTree(kids[i]);
            f.delete();
        } catch (Throwable t) { }
    }

    // <outDir>/Simulation_results/<dirName> con fallback al tag
    String createOutputFolder(String outDir, String dirName, String tag) throws Exception {
        java.io.File root = new java.io.File(outDir, "Simulation_results");
        if (!root.isDirectory() && !root.mkdirs()) throw new Exception("No se pudo crear " + root);
        java.io.File f = new java.io.File(root, dirName);
        if (!dirName.isEmpty() && (f.isDirectory() || f.mkdirs())) return f.getPath();
        f = new java.io.File(root, safeName(tag));
        if (f.isDirectory() || f.mkdirs()) return f.getPath();
        throw new Exception("No se pudo crear la carpeta de salida para " + dirName + " / " + tag);
    }

    String checkWritable(String outDir) {
        try {
            java.io.File root = new java.io.File(outDir, "Simulation_results");
            if (!root.isDirectory() && !root.mkdirs()) return "No se pudo crear " + root;
            java.io.File t = java.io.File.createTempFile("write_test_", ".tmp", root);
            t.delete();
            return "";
        } catch (Throwable e) { return "Sin permisos de escritura en " + outDir + ": " + e.getMessage(); }
    }

    double[] lin(double a, double b, int n) {
        double[] v = new double[n];
        if (n == 1) { v[0] = b; return v; }
        for (int i = 0; i < n; i++) v[i] = a + (b - a) * i / (n - 1);
        v[n - 1] = b;
        return v;
    }

    // Mismo orden que meshgrid(theta, phi) + (:) de MATLAB (phi varia mas rapido)
    double[][] sphere(int nTheta, int nPhi, double r) {
        double[] th = lin(0, 2 * Math.PI, nTheta);
        double[] ph = lin(0, Math.PI, nPhi);
        double[][] c = new double[nTheta * nPhi][3];
        int k = 0;
        for (int i = 0; i < nTheta; i++) {
            for (int j = 0; j < nPhi; j++) {
                c[k][0] = r * Math.sin(ph[j]) * Math.cos(th[i]);
                c[k][1] = r * Math.sin(ph[j]) * Math.sin(th[i]);
                c[k][2] = r * Math.cos(ph[j]);
                k++;
            }
        }
        return c;
    }

    void writeCoords(String path, double[][] c) throws Exception {
        java.io.BufferedWriter w = new java.io.BufferedWriter(new java.io.FileWriter(path));
        try {
            for (int i = 0; i < c.length; i++) w.write(c[i][0] + "\t" + c[i][1] + "\t" + c[i][2] + "\n");
        } finally { w.close(); }
    }

    // Lee un .txt numerico (comentarios con %) y devuelve las 3 columnas elegidas
    double[][] readCoords(String path, int[] cols) throws Exception {
        if (path == null || path.trim().isEmpty() || !new java.io.File(path).isFile())
            throw new Exception("Selecciona un archivo .txt de coordenadas valido.");
        if (cols[0] < 1 || cols[1] < 1 || cols[2] < 1 || cols[0] == cols[1] || cols[0] == cols[2] || cols[1] == cols[2])
            throw new Exception("Las columnas deben ser enteros positivos y distintos.");
        int need = Math.max(cols[0], Math.max(cols[1], cols[2]));
        java.util.List<double[]> rows = new java.util.ArrayList<double[]>();
        int maxCols = 0;
        java.io.BufferedReader br = new java.io.BufferedReader(
            new java.io.InputStreamReader(new java.io.FileInputStream(path), "UTF-8"));
        try {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("%")) continue;
                String[] t = line.split("[\\s,;]+");
                double[] v = new double[t.length];
                boolean ok = true;
                for (int i = 0; i < t.length && ok; i++) {
                    try { v[i] = Double.parseDouble(t[i]); } catch (Exception e) { ok = false; }
                }
                if (!ok) continue;
                maxCols = Math.max(maxCols, t.length);
                rows.add(v);
            }
        } finally { br.close(); }
        if (rows.isEmpty() || maxCols < 3) throw new Exception("El archivo .txt debe contener al menos 3 columnas numericas.");
        if (maxCols < need) throw new Exception("El archivo solo tiene " + maxCols + " columnas y se pidio la columna " + need + ".");
        java.util.List<double[]> out = new java.util.ArrayList<double[]>();
        for (int i = 0; i < rows.size(); i++) {
            double[] v = rows.get(i);
            if (v.length < need) continue;
            double x = v[cols[0] - 1]; double y = v[cols[1] - 1]; double z = v[cols[2] - 1];
            if (Double.isNaN(x) || Double.isInfinite(x) || Double.isNaN(y) || Double.isInfinite(y)
                || Double.isNaN(z) || Double.isInfinite(z)) continue;
            out.add(new double[] {x, y, z});
        }
        if (out.isEmpty()) throw new Exception("No se encontraron coordenadas validas en las columnas seleccionadas.");
        return out.toArray(new double[out.size()][]);
    }

    // Comprueba que el radio exportado por COMSOL coincide con R (mismas tolerancias que el .m)
    void validateExportedRadius(String path, double r) throws Exception {
        double min = Double.POSITIVE_INFINITY; double max = Double.NEGATIVE_INFINITY; int n = 0;
        java.io.BufferedReader br = new java.io.BufferedReader(new java.io.FileReader(path));
        try {
            String line;
            while ((line = br.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("%")) continue;
                String[] t = line.split("\\s+");
                if (t.length < 3) continue;
                try {
                    double x = Double.parseDouble(t[0]); double y = Double.parseDouble(t[1]); double z = Double.parseDouble(t[2]);
                    double rad = Math.sqrt(x * x + y * y + z * z);
                    min = Math.min(min, rad); max = Math.max(max, rad); n++;
                } catch (Exception e) { }
            }
        } finally { br.close(); }
        if (n == 0) throw new Exception("No se pudieron validar las coordenadas exportadas en " + path);
        double tol = Math.max(5e-4, r * 5e-3);
        if (Math.abs(max - r) > tol || Math.abs(min - r) > tol)
            throw new Exception("Radio exportado fuera de tolerancia: R=" + r + " m, min=" + min + " m, max=" + max
                + " m. Revisa la unidad de longitud del modelo.");
    }
}

final Util u = new Util();
final Prefs prefs = new Prefs();
final Log lg = new Log();

// ----------------------------------------------------------------------------
// Interfaz: JOptionPane + paneles Swing
// ----------------------------------------------------------------------------
class Ui {
    // Muestra un JOptionPane en un dialogo siempre visible; devuelve el valor elegido (null si se cierra)
    Object show(String title, Object content, int msgType, int optType, Object[] options) {
        javax.swing.JOptionPane pane = new javax.swing.JOptionPane(content, msgType, optType, null, options,
            options == null ? null : options[0]);
        javax.swing.JDialog d = pane.createDialog(null, title);
        try {
            d.setAlwaysOnTop(true);
        } catch (SecurityException ex) {
            // El sandbox de COMSOL no concede AWTPermission setWindowAlwaysOnTop; se sigue sin esa opcion
        }
        d.setResizable(true);
        d.setVisible(true);
        d.dispose();
        return pane.getValue();
    }

    boolean ok(String title, Object content) {
        Object v = show(title, content, javax.swing.JOptionPane.PLAIN_MESSAGE, javax.swing.JOptionPane.OK_CANCEL_OPTION, null);
        return v instanceof Integer && ((Integer) v).intValue() == javax.swing.JOptionPane.OK_OPTION;
    }

    boolean yesNo(String title, Object content) {
        Object v = show(title, content, javax.swing.JOptionPane.QUESTION_MESSAGE, javax.swing.JOptionPane.YES_NO_OPTION, null);
        return v instanceof Integer && ((Integer) v).intValue() == javax.swing.JOptionPane.YES_OPTION;
    }

    void error(String title, String msg) {
        show(title, msg, javax.swing.JOptionPane.ERROR_MESSAGE, javax.swing.JOptionPane.DEFAULT_OPTION, null);
    }

    void info(String title, Object msg) {
        show(title, msg, javax.swing.JOptionPane.INFORMATION_MESSAGE, javax.swing.JOptionPane.DEFAULT_OPTION, null);
    }

    int choose(String title, String msg, String[] opts) {
        Object v = show(title, msg, javax.swing.JOptionPane.QUESTION_MESSAGE, javax.swing.JOptionPane.DEFAULT_OPTION, opts);
        for (int i = 0; i < opts.length; i++) if (opts[i].equals(v)) return i;
        return -1;
    }

    javax.swing.JPanel column() {
        javax.swing.JPanel p = new javax.swing.JPanel();
        p.setLayout(new javax.swing.BoxLayout(p, javax.swing.BoxLayout.Y_AXIS));
        return p;
    }

    javax.swing.JLabel title(String text) {
        javax.swing.JLabel l = new javax.swing.JLabel(text);
        l.setFont(l.getFont().deriveFont(java.awt.Font.BOLD));
        l.setAlignmentX(java.awt.Component.LEFT_ALIGNMENT);
        return l;
    }

    javax.swing.JPanel row(String label, java.awt.Component c) {
        javax.swing.JPanel p = new javax.swing.JPanel(new java.awt.BorderLayout(8, 0));
        javax.swing.JLabel l = new javax.swing.JLabel(label);
        l.setPreferredSize(new java.awt.Dimension(150, 22));
        p.add(l, java.awt.BorderLayout.WEST);
        p.add(c, java.awt.BorderLayout.CENTER);
        p.setAlignmentX(java.awt.Component.LEFT_ALIGNMENT);
        return p;
    }

    javax.swing.JCheckBox check(String text, boolean v) {
        javax.swing.JCheckBox c = new javax.swing.JCheckBox(text, v);
        c.setAlignmentX(java.awt.Component.LEFT_ALIGNMENT);
        return c;
    }

    javax.swing.JScrollPane scroll(java.awt.Component c, int w, int h) {
        javax.swing.JScrollPane s = new javax.swing.JScrollPane(c);
        s.setPreferredSize(new java.awt.Dimension(w, h));
        s.setAlignmentX(java.awt.Component.LEFT_ALIGNMENT);
        return s;
    }

    // Navegador propio: JFileChooser lee "user.dir" (y usa ShellFolder), lo que el sandbox de COMSOL deniega.
    // Solo se usan rutas absolutas y java.io.File.
    class Nav {
        java.io.File cur;
        boolean dirOnly;
        javax.swing.DefaultListModel<java.io.File> model = new javax.swing.DefaultListModel<java.io.File>();
        javax.swing.JTextField path = new javax.swing.JTextField(40);

        void go(java.io.File f) {
            model.clear();
            cur = f;
            path.setText(f == null ? "" : f.getPath());
            java.io.File[] items;
            try {
                items = f == null ? java.io.File.listRoots() : f.listFiles();
            } catch (SecurityException ex) {
                items = null;
            }
            if (items == null) return;
            java.util.Arrays.sort(items, new java.util.Comparator<java.io.File>() {
                public int compare(java.io.File a, java.io.File b) {
                    boolean da = a.isDirectory(), db = b.isDirectory();
                    if (da != db) return da ? -1 : 1;
                    return a.getName().compareToIgnoreCase(b.getName());
                }
            });
            for (java.io.File it : items) {
                if (f == null || it.isDirectory() || (!dirOnly && it.getName().toLowerCase().endsWith(".txt"))) model.addElement(it);
            }
        }
    }

    // Devuelve la ruta elegida o null si se cancela
    String browse(String title, String start, boolean dirOnly) {
        final Nav nav = new Nav();
        nav.dirOnly = dirOnly;
        java.io.File init = null;
        try {
            if (start != null && !start.trim().isEmpty()) {
                java.io.File s = new java.io.File(start.trim());
                if (s.isAbsolute()) {
                    if (!dirOnly || !s.isDirectory()) s = s.getParentFile();
                    while (s != null && !s.isDirectory()) s = s.getParentFile();
                    init = s;
                }
            }
        } catch (SecurityException ex) {
            init = null;
        }
        nav.go(init);

        final javax.swing.JList<java.io.File> list = new javax.swing.JList<java.io.File>(nav.model);
        list.setSelectionMode(javax.swing.ListSelectionModel.SINGLE_SELECTION);
        list.setCellRenderer(new javax.swing.DefaultListCellRenderer() {
            public java.awt.Component getListCellRendererComponent(javax.swing.JList<?> l, Object v, int i, boolean sel, boolean foc) {
                java.io.File f = (java.io.File) v;
                String n = f.getName().isEmpty() ? f.getPath() : f.getName();
                return super.getListCellRendererComponent(l, f.isDirectory() ? "[" + n + "]" : n, i, sel, foc);
            }
        });
        list.addMouseListener(new java.awt.event.MouseAdapter() {
            public void mouseClicked(java.awt.event.MouseEvent e) {
                if (e.getClickCount() == 2) {
                    java.io.File f = list.getSelectedValue();
                    if (f != null && f.isDirectory()) nav.go(f);
                }
            }
        });
        nav.path.addActionListener(new java.awt.event.ActionListener() {
            public void actionPerformed(java.awt.event.ActionEvent e) {
                java.io.File f = new java.io.File(nav.path.getText().trim());
                if (f.isAbsolute() && f.isDirectory()) nav.go(f);
            }
        });
        javax.swing.JButton up = new javax.swing.JButton("Up");
        up.addActionListener(new java.awt.event.ActionListener() {
            public void actionPerformed(java.awt.event.ActionEvent e) {
                nav.go(nav.cur == null ? null : nav.cur.getParentFile());
            }
        });
        javax.swing.JButton roots = new javax.swing.JButton("Drives");
        roots.addActionListener(new java.awt.event.ActionListener() {
            public void actionPerformed(java.awt.event.ActionEvent e) { nav.go(null); }
        });

        javax.swing.JPanel top = new javax.swing.JPanel(new java.awt.BorderLayout(4, 0));
        javax.swing.JPanel btns = new javax.swing.JPanel(new java.awt.GridLayout(1, 2, 4, 0));
        btns.add(up);
        btns.add(roots);
        top.add(btns, java.awt.BorderLayout.WEST);
        top.add(nav.path, java.awt.BorderLayout.CENTER);

        javax.swing.JPanel p = new javax.swing.JPanel(new java.awt.BorderLayout(0, 4));
        p.add(top, java.awt.BorderLayout.NORTH);
        p.add(scroll(list, 520, 280), java.awt.BorderLayout.CENTER);
        p.add(new javax.swing.JLabel(dirOnly
            ? "Doble clic para entrar; OK elige la carpeta seleccionada (o la actual)."
            : "Doble clic para entrar; seleccione un archivo y pulse OK."), java.awt.BorderLayout.SOUTH);

        if (!ok(title, p)) return null;
        java.io.File sel = list.getSelectedValue();
        if (dirOnly) {
            if (sel != null && sel.isDirectory()) return sel.getAbsolutePath();
            return nav.cur == null ? null : nav.cur.getAbsolutePath();
        }
        return sel != null && sel.isFile() ? sel.getAbsolutePath() : null;
    }

    String chooseDir(String start) {
        return browse("Seleccionar carpeta", start, true);
    }

    String chooseFile(String start) {
        return browse("Seleccionar archivo", start, false);
    }
    javax.swing.JPanel browseRow(String label, final javax.swing.JTextField tf, final boolean dirOnly) {
        javax.swing.JPanel inner = new javax.swing.JPanel(new java.awt.BorderLayout(4, 0));
        inner.add(tf, java.awt.BorderLayout.CENTER);
        javax.swing.JButton b = new javax.swing.JButton("Browse");
        b.addActionListener(new java.awt.event.ActionListener() {
            public void actionPerformed(java.awt.event.ActionEvent e) {
                String r = dirOnly ? chooseDir(tf.getText()) : chooseFile(tf.getText());
                if (r != null) tf.setText(r);
            }
        });
        inner.add(b, java.awt.BorderLayout.EAST);
        return row(label, inner);
    }

    // ---- Menu principal (equivale a la figura principal de la GUI) ----
    boolean askMain(Opts o, java.util.List<Ds> all, java.util.List<Ds> selected) {
        javax.swing.JList<Ds> list = new javax.swing.JList<Ds>(all.toArray(new Ds[0]));
        list.setSelectionMode(javax.swing.ListSelectionModel.MULTIPLE_INTERVAL_SELECTION);

        javax.swing.JTextField tfOut = new javax.swing.JTextField(o.outDir, 32);
        javax.swing.JComboBox<String> cbField = new javax.swing.JComboBox<String>(new String[] {"Bx", "By", "Bz"});
        cbField.setSelectedItem(o.field);
        javax.swing.JTextField tfModel = new javax.swing.JTextField(o.modelName, 32);
        javax.swing.JTextField tfFov = new javax.swing.JTextField(o.fovInfo, 32);
        javax.swing.JTextField tfPy = new javax.swing.JTextField(o.scriptDir, 32);
        javax.swing.JCheckBox cPy = check("Ejecutar postproceso Python (histogramas)", o.runPython);

        javax.swing.JCheckBox c3d = check("B_FOV 3D Plot", o.bfov3d);
        javax.swing.JCheckBox cOrtho = check("Change orthoscale for projections", o.changeOrtho);
        javax.swing.JCheckBox cHist = check("B_FOV Histogram", o.bfovHist);
        javax.swing.JCheckBox cCoord = check("B_FOV Custom Coordinates", o.bfovCoord);
        javax.swing.JCheckBox cFov = check("Change default FOV (elegir selections/dominios)", o.changeFov);
        javax.swing.JCheckBox cM3d = check("Magnets 3D Plot", o.magnets3d);
        javax.swing.JCheckBox cMh = check("Magnets Histogram", o.magnetsHist);

        javax.swing.JPanel p = column();
        p.add(row("Field component:", cbField));
        p.add(javax.swing.Box.createVerticalStrut(6));
        p.add(title("Datasets disponibles (multi-seleccion):"));
        p.add(scroll(list, 520, 130));
        p.add(browseRow("Output dir:", tfOut, true));
        p.add(row("Model name:", tfModel));
        p.add(row("FOV info:", tfFov));
        p.add(javax.swing.Box.createVerticalStrut(6));
        p.add(title("Salidas:"));
        p.add(c3d); p.add(cOrtho); p.add(cHist); p.add(cCoord); p.add(cFov); p.add(cM3d); p.add(cMh);
        p.add(javax.swing.Box.createVerticalStrut(6));
        p.add(cPy);
        p.add(browseRow("Python scripts dir:", tfPy, true));

        while (true) {
            if (!ok("COMSOL Analyzer - Run Extraction", p)) return false;
            java.util.List<Ds> sel = list.getSelectedValuesList();
            String out = tfOut.getText().trim();
            if (sel.isEmpty()) { error("Datasets", "Debe seleccionar al menos un dataset."); continue; }
            if (out.isEmpty()) { error("Output dir", "Debe especificar un directorio de salida."); continue; }
            if (tfModel.getText().trim().isEmpty()) { error("Model name", "Indica un nombre de modelo."); continue; }
            String w = u.checkWritable(out);
            if (!w.isEmpty()) { error("Output dir", w); continue; }
            selected.addAll(sel);
            o.outDir = out;
            o.field = String.valueOf(cbField.getSelectedItem());
            o.modelName = u.safeName(tfModel.getText().trim());
            o.fovInfo = tfFov.getText().trim().isEmpty() ? "N/A" : tfFov.getText().trim();
            o.scriptDir = tfPy.getText().trim();
            o.runPython = cPy.isSelected();
            o.bfov3d = c3d.isSelected(); o.changeOrtho = cOrtho.isSelected(); o.bfovHist = cHist.isSelected();
            o.bfovCoord = cCoord.isSelected(); o.changeFov = cFov.isSelected();
            o.magnets3d = cM3d.isSelected(); o.magnetsHist = cMh.isSelected();
            return true;
        }
    }

    // ---- Parametric Sweep: valores del barrido a analizar (null si se cancela) ----
    java.util.List<Integer> askSweep(Ds ds, SweepInfo si) {
        String[] items = new String[si.count()];
        for (int i = 0; i < items.length; i++) items[i] = (i + 1) + ":  " + si.labels.get(i);
        final javax.swing.JList<String> list = new javax.swing.JList<String>(items);
        list.setSelectionMode(javax.swing.ListSelectionModel.MULTIPLE_INTERVAL_SELECTION);
        list.setSelectionInterval(0, items.length - 1);
        final int n = items.length;
        javax.swing.JButton bAll = new javax.swing.JButton("Seleccionar todo");
        bAll.addActionListener(new java.awt.event.ActionListener() {
            public void actionPerformed(java.awt.event.ActionEvent e) { list.setSelectionInterval(0, n - 1); }
        });
        javax.swing.JButton bNone = new javax.swing.JButton("Limpiar");
        bNone.addActionListener(new java.awt.event.ActionListener() {
            public void actionPerformed(java.awt.event.ActionEvent e) { list.clearSelection(); }
        });
        javax.swing.JPanel btns = new javax.swing.JPanel(new java.awt.FlowLayout(java.awt.FlowLayout.LEFT, 4, 0));
        btns.add(bAll); btns.add(bNone);
        btns.setAlignmentX(java.awt.Component.LEFT_ALIGNMENT);

        javax.swing.JPanel p = column();
        p.add(title("Parametric Sweep en \"" + ds.shortLabel + "\" [" + ds.tag + "]"));
        p.add(new javax.swing.JLabel("Selecciona los valores a analizar (cada uno se procesa como un estudio independiente):"));
        p.add(scroll(list, 460, 240));
        p.add(btns);
        while (true) {
            if (!ok("Parametric Sweep", p)) return null;
            int[] idx = list.getSelectedIndices();
            if (idx.length == 0) { error("Seleccion requerida", "Selecciona al menos un valor del barrido."); continue; }
            java.util.List<Integer> out = new java.util.ArrayList<Integer>();
            for (int i = 0; i < idx.length; i++) out.add(Integer.valueOf(idx[i]));
            return out;
        }
    }

    // ---- Change default FOV: selections + salidas de dominio ----
    boolean askDomains(Opts o) {
        java.util.List<Sel> sels = u.selections();
        if (sels.isEmpty()) {
            error("Selections no encontradas",
                "No se encontraron selections en Component 1 > Definitions > Selections.");
            return false;
        }
        javax.swing.JList<Sel> list = new javax.swing.JList<Sel>(sels.toArray(new Sel[0]));
        javax.swing.JCheckBox c3d = check("B_Domain 3D Plot", true);
        javax.swing.JCheckBox cH = check("B_Domain Histogram", true);
        javax.swing.JCheckBox cC = check("B_Domain Custom Coordinates", false);
        javax.swing.JPanel p = column();
        p.add(title("Selections (Component 1 > Definitions > Selections):"));
        p.add(scroll(list, 460, 220));
        p.add(c3d); p.add(cH); p.add(cC);
        while (true) {
            if (!ok("Change default FOV", p)) return false;
            if (list.getSelectedValuesList().isEmpty()) { error("Seleccion requerida", "Selecciona al menos una selection."); continue; }
            if (!c3d.isSelected() && !cH.isSelected() && !cC.isSelected()) {
                error("Salida requerida", "Selecciona al menos una salida de dominio."); continue;
            }
            o.domains = new java.util.ArrayList<Sel>(list.getSelectedValuesList());
            o.domainMode = true;
            o.bfov3d = c3d.isSelected(); o.bfovHist = cH.isSelected(); o.bfovCoord = cC.isSelected();
            return true;
        }
    }

    // ---- Extract Geometry Plots: selections a ocultar (puede ser ninguna) ----
    boolean askHideSelections(java.util.List<Sel> hide) {
        java.util.List<Sel> sels = u.selections();
        if (sels.isEmpty()) {
            error("Selections no encontradas", "No se encontraron selections en Component 1 > Definitions > Selections.");
            return false;
        }
        javax.swing.JList<Sel> list = new javax.swing.JList<Sel>(sels.toArray(new Sel[0]));
        javax.swing.JPanel p = column();
        p.add(title("Domains to hide (Definitions > Selections):"));
        p.add(scroll(list, 460, 280));
        if (!ok("Extract Geometry Plots", p)) return false;
        hide.addAll(list.getSelectedValuesList());
        return true;
    }

    boolean askOrthoScale(Opts o) {
        javax.swing.JTextField tf = new javax.swing.JTextField(String.valueOf(prefs.d("ProjectionOrthoScale", 0.35)), 12);
        while (true) {
            if (!ok("Projection orthoscale", row("Orthoscale (>0):", tf))) return false;
            Double v = u.num(tf.getText());
            if (v == null || v.doubleValue() <= 0) { error("Valor invalido", "Orthoscale debe ser un numero mayor que 0."); continue; }
            o.orthoScale = v.doubleValue();
            prefs.put("ProjectionOrthoScale", o.orthoScale);
            return true;
        }
    }

    boolean askHistBins(Opts o) {
        javax.swing.JTextField tf = new javax.swing.JTextField(String.valueOf((int) prefs.d("HistogramBins", 100)), 12);
        while (true) {
            if (!ok("B_FOV Histogram", row("Number of bins:", tf))) return false;
            Integer v = u.integer(tf.getText());
            if (v == null || v.intValue() < 1) { error("Valor invalido", "El valor de bins debe ser un entero positivo."); continue; }
            o.histBins = v.intValue();
            prefs.put("HistogramBins", o.histBins);
            return true;
        }
    }

    // ---- B_FOV Custom Coordinates (esferica o desde archivo) ----
    boolean askCoordinates(Opts o) {
        final javax.swing.JComboBox<String> mode = new javax.swing.JComboBox<String>(new String[] {"Spherical coordinates", "From file"});
        final javax.swing.JTextField tNt = new javax.swing.JTextField(String.valueOf((int) prefs.d("Coord_nTheta", 100)), 10);
        final javax.swing.JTextField tNp = new javax.swing.JTextField(String.valueOf((int) prefs.d("Coord_nPhi", 100)), 10);
        final javax.swing.JTextField tR = new javax.swing.JTextField(String.valueOf(prefs.d("Coord_R", 0.1)), 10);
        final javax.swing.JTextField tFile = new javax.swing.JTextField("", 24);
        final javax.swing.JTextField tX = new javax.swing.JTextField("1", 4);
        final javax.swing.JTextField tY = new javax.swing.JTextField("2", 4);
        final javax.swing.JTextField tZ = new javax.swing.JTextField("3", 4);
        javax.swing.JPanel cols = new javax.swing.JPanel(new java.awt.FlowLayout(java.awt.FlowLayout.LEFT, 4, 0));
        cols.add(tX); cols.add(tY); cols.add(tZ);

        final javax.swing.JButton[] browse = new javax.swing.JButton[1];
        javax.swing.JPanel fileRow = browseRow("Coordinate file:", tFile, false);
        java.awt.Component[] kids = ((javax.swing.JPanel) fileRow.getComponent(1)).getComponents();
        for (int i = 0; i < kids.length; i++) if (kids[i] instanceof javax.swing.JButton) browse[0] = (javax.swing.JButton) kids[i];

        final javax.swing.JTextField[] sph = new javax.swing.JTextField[] {tNt, tNp, tR};
        final javax.swing.JTextField[] fil = new javax.swing.JTextField[] {tFile, tX, tY, tZ};
        java.awt.event.ActionListener toggle = new java.awt.event.ActionListener() {
            public void actionPerformed(java.awt.event.ActionEvent e) {
                boolean f = "From file".equals(mode.getSelectedItem());
                for (int i = 0; i < sph.length; i++) sph[i].setEnabled(!f);
                for (int i = 0; i < fil.length; i++) fil[i].setEnabled(f);
                browse[0].setEnabled(f);
            }
        };
        mode.addActionListener(toggle);
        toggle.actionPerformed(null);

        javax.swing.JPanel p = column();
        p.add(title("B_FOV Custom Coordinates"));
        p.add(row("Model selection:", mode));
        p.add(row("n_theta:", tNt));
        p.add(row("n_phi:", tNp));
        p.add(row("R [m]:", tR));
        p.add(fileRow);
        p.add(row("Columns x / y / z:", cols));

        while (true) {
            if (!ok("B_FOV Custom Coordinates", p)) return false;
            CoordCfg c = new CoordCfg();
            String preview;
            try {
                if ("From file".equals(mode.getSelectedItem())) {
                    Integer cx = u.integer(tX.getText()); Integer cy = u.integer(tY.getText()); Integer cz = u.integer(tZ.getText());
                    if (cx == null || cy == null || cz == null) throw new Exception("Las columnas deben ser enteros.");
                    c.fromFile = true; c.filePath = tFile.getText().trim();
                    c.cols = new int[] {cx.intValue(), cy.intValue(), cz.intValue()};
                    c.coords = u.readCoords(c.filePath, c.cols);
                    preview = "Coordenadas desde archivo: " + c.filePath + "\nColumnas " + c.cols[0] + ", " + c.cols[1] + ", "
                        + c.cols[2] + " | puntos = " + c.coords.length;
                } else {
                    Integer nt = u.integer(tNt.getText()); Integer np = u.integer(tNp.getText()); Double r = u.num(tR.getText());
                    if (nt == null || np == null || r == null || nt.intValue() < 1 || np.intValue() < 1 || r.doubleValue() <= 0)
                        throw new Exception("Completa valores validos para n_theta, n_phi (enteros >= 1) y R (> 0).");
                    c.nTheta = nt.intValue(); c.nPhi = np.intValue(); c.R = r.doubleValue();
                    c.coords = u.sphere(c.nTheta, c.nPhi, c.R);
                    preview = "Coordenadas esfericas: nTheta=" + c.nTheta + ", nPhi=" + c.nPhi + ", R=" + c.R
                        + " m | puntos = " + c.coords.length;
                }
            } catch (Exception ex) {
                error("Valores invalidos", ex.getMessage());
                continue;
            }
            StringBuilder sb = new StringBuilder(preview).append("\n\nPrimeros puntos (x, y, z):\n");
            for (int i = 0; i < Math.min(5, c.coords.length); i++)
                sb.append(String.format(java.util.Locale.ROOT, "  %.6g   %.6g   %.6g\n", c.coords[i][0], c.coords[i][1], c.coords[i][2]));
            sb.append("\nContinuar con esta configuracion?");
            if (!yesNo("Preview Custom Coordinates", sb.toString())) continue;
            o.coord = c;
            if (!c.fromFile) {
                prefs.put("Coord_nTheta", c.nTheta); prefs.put("Coord_nPhi", c.nPhi); prefs.put("Coord_R", c.R);
            }
            return true;
        }
    }

    // ---- Magnets Histogram: normM / normH ----
    boolean askMagnets(Opts o) {
        final javax.swing.JCheckBox cM = check("normM", true);
        final javax.swing.JCheckBox cH = check("normH", false);
        final javax.swing.JTextField tBins = new javax.swing.JTextField(String.valueOf((int) prefs.d("MagnetsHistogramBins", 100)), 10);
        final javax.swing.JTextField tStep = new javax.swing.JTextField(String.valueOf(prefs.d("MagnetsHistogramStepPercent", 2)), 10);
        final javax.swing.JTextField tBr = new javax.swing.JTextField(String.valueOf(prefs.d("MagnetsHistogramBr", 1.4)), 10);
        final javax.swing.JTextField tHcb = new javax.swing.JTextField("0", 10);
        final javax.swing.JTextField tHcj = new javax.swing.JTextField("0", 10);
        final javax.swing.JTextField tHk = new javax.swing.JTextField("0", 10);
        final javax.swing.JTextField tHl = new javax.swing.JTextField("0", 10);
        final javax.swing.JTextArea tExtra = new javax.swing.JTextArea(4, 24);
        final javax.swing.JTextField[] mF = new javax.swing.JTextField[] {tStep, tBr};
        final javax.swing.JTextField[] hF = new javax.swing.JTextField[] {tHcb, tHcj, tHk, tHl};
        java.awt.event.ActionListener toggle = new java.awt.event.ActionListener() {
            public void actionPerformed(java.awt.event.ActionEvent e) {
                for (int i = 0; i < mF.length; i++) mF[i].setEnabled(cM.isSelected());
                for (int i = 0; i < hF.length; i++) hF[i].setEnabled(cH.isSelected());
                tExtra.setEnabled(cH.isSelected());
            }
        };
        cM.addActionListener(toggle); cH.addActionListener(toggle);
        toggle.actionPerformed(null);

        javax.swing.JPanel p = column();
        p.add(title("Magnets Histogram outputs:"));
        p.add(cM); p.add(cH);
        p.add(row("Histogram bins (shared):", tBins));
        p.add(title("normM postprocess:"));
        p.add(row("Step percent (%):", tStep));
        p.add(row("Br (Tesla):", tBr));
        p.add(title("normH thresholds (kA/m):"));
        p.add(row("Hcb:", tHcb)); p.add(row("Hcj:", tHcj));
        p.add(row("Hknee:", tHk)); p.add(row("Hlinear_end:", tHl));
        p.add(title("Additional H values (una por linea: nombre=valor):"));
        p.add(scroll(tExtra, 420, 80));

        while (true) {
            if (!ok("Magnets Histogram", p)) return false;
            MagCfg m = new MagCfg();
            m.normM = cM.isSelected(); m.normH = cH.isSelected();
            if (!m.normM && !m.normH) { error("Seleccion requerida", "Selecciona al menos una salida: normM o normH."); continue; }
            Integer bins = u.integer(tBins.getText());
            if (bins == null || bins.intValue() < 1) { error("Valor invalido", "El valor de bins debe ser un entero positivo."); continue; }
            m.bins = bins.intValue();
            String bad = null;
            if (m.normM) {
                Double st = u.num(tStep.getText()); Double br = u.num(tBr.getText());
                if (st == null || st.doubleValue() <= 0) bad = "El valor de step_percent debe ser mayor a 0.";
                else if (br == null || br.doubleValue() <= 0) bad = "El valor de Br debe ser mayor a 0.";
                else { m.step = st.doubleValue(); m.br = br.doubleValue(); }
            }
            if (bad == null && m.normH) {
                Double a = u.num(tHcb.getText()); Double b = u.num(tHcj.getText());
                Double c = u.num(tHk.getText()); Double d = u.num(tHl.getText());
                if (a == null) bad = "Hcb debe ser numerico (kA/m).";
                else if (b == null) bad = "Hcj debe ser numerico (kA/m).";
                else if (c == null) bad = "Hknee debe ser numerico (kA/m).";
                else if (d == null) bad = "Hlinear_end debe ser numerico (kA/m).";
                else {
                    m.hcb = a.doubleValue(); m.hcj = b.doubleValue(); m.hknee = c.doubleValue(); m.hlinearEnd = d.doubleValue();
                    String[] lines = tExtra.getText().split("\\r?\\n");
                    for (int i = 0; i < lines.length && bad == null; i++) {
                        String ln = lines[i].trim();
                        if (ln.isEmpty()) continue;
                        int k = ln.indexOf('=');
                        Double v = k > 0 ? u.num(ln.substring(k + 1)) : null;
                        if (k <= 0 || ln.substring(0, k).trim().isEmpty() || v == null) {
                            bad = "Fila " + (i + 1) + " de Additional H values invalida (formato nombre=valor).";
                        } else {
                            ExtraH x = new ExtraH(); x.name = ln.substring(0, k).trim(); x.value = v.doubleValue();
                            m.extra.add(x);
                        }
                    }
                }
            }
            if (bad != null) { error("Valor invalido", bad); continue; }
            o.mag = m;
            prefs.put("MagnetsHistogramBins", m.bins);
            if (m.normM) { prefs.put("MagnetsHistogramStepPercent", m.step); prefs.put("MagnetsHistogramBr", m.br); }
            return true;
        }
    }
}

final Ui ui = new Ui();

// ----------------------------------------------------------------------------
// Exportaciones COMSOL (export_dataset, export_magnets_*, export_custom_coordinates,
// export_geometry_plots)
// ----------------------------------------------------------------------------
class Exporter {
    void rmExport(String tag) { try { model.result().export().remove(tag); } catch (Throwable t) { } }
    void rmPlot(String tag) { try { model.result().remove(tag); } catch (Throwable t) { } }
    void rmDataset(String tag) { try { model.result().dataset().remove(tag); } catch (Throwable t) { } }

    // Valor del Parametric Sweep (1-based) a aplicar via "looplevel" en plots/exports; 0 = sin seleccion
    int loop = 0;

    String propList(Object target) {
        String[] props = u.strArr(u.call(target, "properties"));
        StringBuilder sb = new StringBuilder();
        for (int i = 0; props != null && i < props.length; i++) sb.append(i > 0 ? "," : "").append(props[i]);
        return sb.toString();
    }

    // Prueba varias formas de fijar looplevel; "" si alguna funciona, si no el detalle de los fallos
    String setLoop(Object target) {
        StringBuilder err = new StringBuilder();
        u.call(target, "setIndex", "looplevelinput", "manual", Integer.valueOf(0));
        if (u.lastErr.isEmpty()) {
            u.call(target, "setIndex", "looplevel", String.valueOf(loop), Integer.valueOf(0));
            if (u.lastErr.isEmpty()) return "";
            u.call(target, "setIndex", "looplevel", Integer.valueOf(loop), Integer.valueOf(0));
            if (u.lastErr.isEmpty()) return "";
            err.append("setIndex(looplevel): ").append(u.lastErr).append(" | ");
        } else err.append("setIndex(looplevelinput): ").append(u.lastErr).append(" | ");
        u.call(target, "set", "looplevelinput", new String[] {"manual"});
        if (u.lastErr.isEmpty()) {
            u.call(target, "set", "looplevel", new int[] {loop});
            if (u.lastErr.isEmpty()) return "";
            err.append("set(looplevel): ").append(u.lastErr).append(" | ");
        } else err.append("set(looplevelinput): ").append(u.lastErr).append(" | ");
        u.call(target, "set", "looplevel", new int[] {loop});
        if (u.lastErr.isEmpty()) return "";
        err.append("set(looplevel sin input): ").append(u.lastErr);
        return err.toString();
    }

    void loopPlot(String tag) throws Exception {
        if (loop <= 0) return;
        try { model.result(tag).run(); } catch (Throwable t) { }
        String e = setLoop(model.result(tag));
        if (!e.isEmpty())
            throw new Exception("No se pudo fijar looplevel=" + loop + " en el plot " + tag + ": " + e
                + ". Propiedades del plot: " + propList(model.result(tag)));
    }

    void loopExport(String tag) throws Exception {
        if (loop <= 0) return;
        String e = setLoop(model.result().export(tag));
        if (!e.isEmpty())
            throw new Exception("No se pudo fijar looplevel=" + loop + " en el export " + tag + ": " + e
                + ". Propiedades del export: " + propList(model.result().export(tag)));
    }

    void ensureView2() {
        try { model.component("comp1").view("view2"); }
        catch (Throwable t) { model.component("comp1").view().create("view2", "geom1"); }
    }

    // Zoom to extents de la vista (la API puede no exponerlo; el export con "zoomextents" actua como respaldo)
    void fitView(String viewTag) {
        try { u.call(model.component("comp1").view(viewTag).camera(), "zoomExtents"); } catch (Throwable t) { }
    }

    void configureImage(String tag, String lockview, boolean fit) {
        String[][] kv = {
            {"size", "current"}, {"unit", "px"}, {"height", "600"}, {"width", "800"}, {"lockratio", "off"},
            {"resolution", "96"}, {"antialias", "on"}, {"zoomextents", fit ? "on" : "off"}, {"fontsize", "12"},
            {"colortheme", "globaltheme"}, {"background", "color"}, {"gltfincludelines", "on"},
            {"title1d", "on"}, {"legend1d", "on"}, {"logo1d", "on"}, {"options1d", "on"},
            {"title2d", "on"}, {"legend2d", "on"}, {"logo2d", "on"}, {"options2d", "off"},
            {"title3d", "on"}, {"legend3d", "on"}, {"logo3d", "on"}, {"options3d", "on"},
            {"axisorientation", "on"}, {"grid", "on"}, {"axes1d", "on"}, {"axes2d", "on"}, {"showgrid", "on"},
            {"target", "file"}, {"qualitylevel", "92"}, {"qualityactive", "off"}, {"imagetype", "png"},
            {"lockview", lockview}, {"highprecisioncolor", "off"}
        };
        for (int i = 0; i < kv.length; i++) model.result().export(tag).set(kv[i][0], kv[i][1]);
        model.result().export(tag).set("customcolor", new int[] {1, 1, 1});
    }

    // PNG nativo de COMSOL a ruta temporal corta y movido al destino final.
    // fit3d: encuadra la vista 3D (zoom to extents) justo antes de renderizar
    void exportPng(String pgTag, String imgTag, String pngOut, boolean fit3d) throws Exception {
        java.io.File tmp = u.tempFile("png", imgTag);
        try {
            rmExport(imgTag);
            model.result().export().create(imgTag, pgTag, "Image");
            configureImage(imgTag, "off", fit3d);
            if (fit3d) {
                try { model.result(pgTag).run(); } catch (Throwable t) { }
                fitView("view1");
            }
            model.result().export(imgTag).set("pngfilename", tmp.getPath());
            model.result().export(imgTag).run();
            rmExport(imgTag);
            try { model.result(pgTag).run(); model.result(pgTag).run(); } catch (Throwable t) { }
            u.move(tmp.getPath(), pngOut);
        } finally { tmp.delete(); }
    }

    String[] orthoPaths(String mainPng) {
        java.io.File f = new java.io.File(mainPng);
        String name = f.getName();
        String ext = "";
        int dot = name.lastIndexOf('.');
        if (dot >= 0) { ext = name.substring(dot); name = name.substring(0, dot); }
        String base = name.replaceAll("_3DPlot$", "");
        if (base.equals(name)) base = name.replaceAll("3DPlot$", "");
        String dir = f.getParent() == null ? "" : f.getParent();
        return new String[] {new java.io.File(dir, base + "_XY" + ext).getPath(),
            new java.io.File(dir, base + "_YZ" + ext).getPath(), new java.io.File(dir, base + "_XZ" + ext).getPath()};
    }

    void orthoExport(String imgTag, String outPath, String tmpTag) throws Exception {
        java.io.File tmp = u.tempFile("png", tmpTag);
        try {
            model.result().export(imgTag).set("pngfilename", tmp.getPath());
            model.result().export(imgTag).run();
            u.move(tmp.getPath(), outPath);
        } finally { tmp.delete(); }
    }

    // scale <= 0: encuadre automatico (zoom to extents); scale > 0: orthoscale manual
    void camera(String projection, double[] pos, double[] up, double scale) {
        model.component("comp1").view("view2").camera().set("projection", projection);
        model.component("comp1").view("view2").camera().set("position", pos);
        model.component("comp1").view("view2").camera().set("up", up);
        if (scale > 0) model.component("comp1").view("view2").camera().set("orthoscale", scale);
        else fitView("view2");
    }

    // Vistas ortograficas XY / YZ / XZ del PlotGroup3D
    void orthographicViews(String pg3d, String imgTag, String mainPng, String dsTag, double scale) throws Exception {
        String[] paths = orthoPaths(mainPng);
        for (int i = 0; i < paths.length; i++) u.ensureParent(paths[i]);
        ensureView2();
        try { model.result(pg3d).set("view", "view2"); } catch (Throwable t) { }
        rmExport(imgTag);
        model.result().export().create(imgTag, pg3d, "Image");
        configureImage(imgTag, "on", scale <= 0);
        try { model.result().export(imgTag).set("view", "view2"); } catch (Throwable t) { }
        try {
            camera("orthographic", new double[] {0, 0, 1}, new double[] {0, 1, 0}, scale);
            try { model.result(pg3d).run(); } catch (Throwable t) { }
            if (scale <= 0) fitView("view2");
            orthoExport(imgTag, paths[0], dsTag + "_xy");

            camera("orthographic", new double[] {1, 0, 0}, new double[] {0, 0, 1}, scale);
            try { model.result(pg3d).run(); } catch (Throwable t) { }
            if (scale <= 0) fitView("view2");
            orthoExport(imgTag, paths[1], dsTag + "_yz");

            camera("orthographic", new double[] {0, 1, 0}, new double[] {0, 0, 1}, scale);
            try { model.result(pg3d).run(); } catch (Throwable t) { }
            if (scale <= 0) fitView("view2");
            orthoExport(imgTag, paths[2], dsTag + "_xz");
        } finally { rmExport(imgTag); }
    }

    // B_FOV (o dominio elegido): PNG 3D + proyecciones + TXT 3D + TXT histograma (componente "field" en mT).
    // ortho <= 0: proyecciones con encuadre automatico
    void exportDataset(String dsTag, String histTxt, String pngPath, String selTagIn, String selLabel,
                       int histBins, double ortho, String field) throws Exception {
        String expr = "mfnc." + field;
        String newDs = "dset_fov_" + dsTag, ds3d = "dset_fov3d_" + dsTag, pg3d = "pg3d_" + dsTag;
        String img = "img_" + dsTag, plot3d = "plot3d_" + dsTag, pg1d = "pg1d_" + dsTag, plotHist = "plothist_" + dsTag;
        try {
            cleanup(newDs, ds3d, pg3d, img, plot3d, pg1d, plotHist);
            if (!u.datasetExists(dsTag)) throw new Exception("El dataset " + dsTag + " no existe en model.result().dataset().");

            String sel = selTagIn == null ? "" : selTagIn.trim();
            if (sel.isEmpty()) {
                sel = u.findSelectionByLabel("FOV");
                if (sel.isEmpty())
                    throw new Exception("No se encontro selection con label \"FOV\" en Definitions (comp1). Selections: " + u.listSelections());
            } else if (!u.selectionExists(sel)) {
                throw new Exception("No se encontro la selection \"" + sel + "\". Selections: " + u.listSelections());
            }

            model.result().dataset().duplicate(newDs, dsTag);
            model.result().dataset(newDs).selection().geom("geom1", 3);
            model.result().dataset(newDs).selection().named(sel);

            // 3D: dataset temporal dedicado
            try { model.component("comp1").view("view1").hideObjects().clear(); } catch (Throwable t) { }
            model.result().dataset().duplicate(ds3d, dsTag);
            model.result().dataset(ds3d).selection().geom("geom1", 3);
            model.result().dataset(ds3d).selection().named(sel);

            model.result().create(pg3d, "PlotGroup3D");
            if (selLabel != null && !selLabel.isEmpty()) model.result(pg3d).label(selLabel);
            try { model.result(pg3d).run(); } catch (Throwable t) { }
            model.result(pg3d).set("data", ds3d);
            loopPlot(pg3d);
            model.result(pg3d).create("vol1", "Volume");
            model.result(pg3d).feature("vol1").set("evaluationsettings", "parent");
            model.result(pg3d).feature("vol1").set("expr", expr);
            model.result(pg3d).feature("vol1").set("unit", "mT");
            model.result(pg3d).feature("vol1").set("colortable", "Inferno");
            model.result(pg3d).run();
            model.component("comp1").view("view1").set("transparency", false);

            try {
                model.result(pg3d).feature("vol1").create("mrkr1", "Marker");
                model.result(pg3d).run();
            } catch (Throwable t) { }

            u.ensureParent(pngPath);
            exportPng(pg3d, img, pngPath, true);
            try { orthographicViews(pg3d, img, pngPath, dsTag, ortho); }
            catch (Throwable t) { lg.log("WARN", dsTag, "Proyecciones ortograficas no exportadas: " + t.getMessage()); }

            // TXT del plot 3D (vol1): mismo nombre que el PNG con extension .txt
            String txt3d = pngPath.replaceAll("\\.[^.\\\\/]*$", "") + ".txt";
            model.result().export().create(plot3d, pg3d, "vol1", "Plot");
            model.result().export(plot3d).set("filename", txt3d);
            model.result().export(plot3d).run();

            // Histograma + TXT principal
            model.result().create(pg1d, "PlotGroup1D");
            model.result(pg1d).run();
            model.result(pg1d).set("data", newDs);
            loopPlot(pg1d);
            model.result(pg1d).create("hist1", "Histogram");
            model.result(pg1d).feature("hist1").set("markerpos", "datapoints");
            model.result(pg1d).feature("hist1").set("linewidth", "preference");
            model.result(pg1d).feature("hist1").set("evaluationsettings", "parent");
            model.result(pg1d).feature("hist1").set("expr", expr);
            model.result(pg1d).feature("hist1").set("unit", "mT");
            model.result(pg1d).feature("hist1").set("number", histBins);
            model.result(pg1d).feature("hist1").set("function", "discrete");
            model.result(pg1d).run();
            model.result().export().create(plotHist, pg1d, "hist1", "Plot");
            model.result().export(plotHist).set("filename", histTxt);
            model.result().export(plotHist).run();
        } catch (Exception ex) {
            throw new Exception("Error exportando dataset \"" + dsTag + "\": " + ex.getMessage(), ex);
        } finally {
            cleanup(newDs, ds3d, pg3d, img, plot3d, pg1d, plotHist);
        }
    }

    void cleanup(String newDs, String ds3d, String pg3d, String img, String plot3d, String pg1d, String plotHist) {
        rmExport(plotHist); rmExport(plot3d); rmExport(img);
        rmPlot(pg1d); rmPlot(pg3d);
        rmDataset(ds3d); rmDataset(newDs);
    }

    // Magnets 3D: PNG + proyecciones + TXT (mu0_const*mfnc.normM en T)
    void exportMagnets3d(String dsTag, String pngPath, String txtPath) throws Exception {
        String newDs = "dset_magnets3d_" + dsTag, pg3d = "pg3d_magnets_" + dsTag;
        String img = "img_magnets_" + dsTag, plot3d = "plot3d_magnets_" + dsTag;
        try {
            rmExport(plot3d); rmExport(img); rmPlot(pg3d); rmDataset(newDs);
            String mag = u.findSelectionByLabel("Magnets");
            if (mag.isEmpty())
                throw new Exception("No se encontro selection con label \"Magnets\" en Definitions (comp1). Selections: " + u.listSelections());

            model.result().dataset().duplicate(newDs, dsTag);
            model.result().dataset(newDs).selection().geom("geom1", 3);
            model.result().dataset(newDs).selection().named(mag);

            model.result().create(pg3d, "PlotGroup3D");
            try { model.result(pg3d).run(); } catch (Throwable t) { }
            model.result(pg3d).set("data", newDs);
            loopPlot(pg3d);
            model.result(pg3d).set("titletype", "manual");
            model.result(pg3d).set("title", "M (T)");
            model.result(pg3d).create("vol1", "Volume");
            model.result(pg3d).feature("vol1").set("evaluationsettings", "parent");
            model.result(pg3d).feature("vol1").set("expr", "mu0_const*mfnc.normM");
            model.result(pg3d).feature("vol1").set("unit", "T");
            model.result(pg3d).feature("vol1").set("colortable", "Inferno");
            model.result(pg3d).run();
            model.result(pg3d).feature("vol1").create("mrkr1", "Marker");
            model.result(pg3d).feature("vol1").feature("mrkr1").set("pointradius", 5);
            model.result(pg3d).run();

            u.ensureParent(pngPath);
            exportPng(pg3d, img, pngPath, true);
            try { orthographicViews(pg3d, img, pngPath, dsTag, -1); }
            catch (Throwable t) { lg.log("WARN", dsTag, "Proyecciones ortograficas Magnets no exportadas: " + t.getMessage()); }

            u.ensureParent(txtPath);
            model.result().export().create(plot3d, pg3d, "vol1", "Plot");
            model.result().export(plot3d).set("filename", txtPath);
            model.result().export(plot3d).run();
        } catch (Exception ex) {
            throw new Exception("Error al exportar Magnets 3D plot para \"" + dsTag + "\": " + ex.getMessage(), ex);
        } finally {
            rmExport(plot3d); rmExport(img); rmPlot(pg3d); rmDataset(newDs);
        }
    }

    // Histograma de Magnets (expr/unit configurables: normM en T o normH en kA/m)
    void exportMagnetsHistogram(String dsTag, String txtPath, String pngPath, int bins, String expr, String unit) throws Exception {
        String newDs = "dset_magnets_hist_" + dsTag, pg1d = "pg1d_magnets_hist_" + dsTag;
        String plotHist = "plothist_magnets_" + dsTag, imgTag = "img_magnets_hist_" + dsTag;
        try {
            rmExport(plotHist); rmExport(imgTag); rmPlot(pg1d); rmDataset(newDs);
            String mag = u.findSelectionByLabel("Magnets");
            if (mag.isEmpty())
                throw new Exception("No se encontro selection con label \"Magnets\" en Definitions (comp1). Selections: " + u.listSelections());

            model.result().dataset().duplicate(newDs, dsTag);
            model.result().dataset(newDs).selection().geom("geom1", 3);
            model.result().dataset(newDs).selection().named(mag);

            model.result().create(pg1d, "PlotGroup1D");
            try { model.result(pg1d).run(); } catch (Throwable t) { }
            model.result(pg1d).set("data", newDs);
            loopPlot(pg1d);
            model.result(pg1d).create("hist1", "Histogram");
            model.result(pg1d).feature("hist1").set("markerpos", "datapoints");
            model.result(pg1d).feature("hist1").set("linewidth", "preference");
            model.result(pg1d).feature("hist1").set("evaluationsettings", "parent");
            model.result(pg1d).feature("hist1").set("expr", expr);
            model.result(pg1d).feature("hist1").set("unit", unit);
            model.result(pg1d).feature("hist1").set("number", bins);
            model.result(pg1d).feature("hist1").set("function", "discrete");
            model.result(pg1d).run();

            model.result().export().create(plotHist, pg1d, "hist1", "Plot");
            model.result().export(plotHist).set("filename", txtPath);
            model.result().export(plotHist).run();

            // PNG opcional: el postproceso Python lo sobrescribe con la version final
            try { exportPng(pg1d, imgTag, pngPath, false); }
            catch (Throwable t) { lg.log("WARN", dsTag, "PNG nativo del histograma no exportado: " + t.getMessage()); }
        } catch (Exception ex) {
            throw new Exception("Error al exportar histograma Magnets para \"" + dsTag + "\": " + ex.getMessage(), ex);
        } finally {
            rmExport(plotHist); rmExport(imgTag); rmPlot(pg1d); rmDataset(newDs);
        }
    }

    // B_FOV en coordenadas custom: TXT con Bx, By, Bz, normB (mT) en los puntos dados
    String exportCustomCoordinates(String dsTag, String outDir, CoordCfg c, String selTag) throws Exception {
        String safeDs = dsTag.replaceAll("[^a-zA-Z0-9_]", "_");
        String tempDs = "dset_coord_" + safeDs, exportTag = "data_" + safeDs;
        String baseTag;
        if (c.fromFile) {
            String fname = new java.io.File(c.filePath).getName().replaceAll("\\.[^.]*$", "");
            baseTag = "FromFile_" + u.safeName(fname) + "_cols_" + c.cols[0] + "_" + c.cols[1] + "_" + c.cols[2];
        } else {
            baseTag = "Spherical_coord_ntheta_" + c.nTheta + "_nphi_" + c.nPhi + "_R" + u.mmToken(c.R * 1000) + "mm";
        }
        String outName = (c.outputBaseName == null || c.outputBaseName.isEmpty()) ? "B_coordinates_" + baseTag : c.outputBaseName;
        String outPath = new java.io.File(outDir, outName + ".txt").getPath();

        java.io.File coordFile = u.tempFile("txt", "coord_" + dsTag);
        java.io.File dataFile = u.tempFile("txt", "data_" + dsTag);
        try {
            u.ensureParent(outPath);
            u.writeCoords(coordFile.getPath(), c.coords);
            rmExport(exportTag);
            String working = dsTag;
            if (selTag != null && !selTag.isEmpty()) {
                rmDataset(tempDs);
                model.result().dataset().duplicate(tempDs, dsTag);
                model.result().dataset(tempDs).selection().geom("geom1", 3);
                model.result().dataset(tempDs).selection().named(selTag);
                working = tempDs;
            }
            model.result().export().create(exportTag, "Data");
            model.result().export(exportTag).set("data", working);
            loopExport(exportTag);
            model.result().export(exportTag).set("location", "file");
            model.result().export(exportTag).set("coordfilename", coordFile.getPath());
            model.result().export(exportTag).set("expr", new String[] {"mfnc.Bx", "mfnc.By", "mfnc.Bz", "mfnc.normB"});
            model.result().export(exportTag).set("unit", new String[] {"mT", "mT", "mT", "mT"});
            model.result().export(exportTag).set("descr", new String[] {"Bx", "By", "Bz", "normB"});
            model.result().export(exportTag).set("filename", dataFile.getPath());
            model.result().export(exportTag).run();
            if (!c.fromFile) u.validateExportedRadius(dataFile.getPath(), c.R);
            u.move(dataFile.getPath(), outPath);
        } catch (Exception ex) {
            throw new Exception("Error exportando coordenadas custom para \"" + dsTag + "\": " + ex.getMessage(), ex);
        } finally {
            rmExport(exportTag); rmDataset(tempDs);
            coordFile.delete(); dataFile.delete();
        }
        return outPath;
    }

    // Geometry_3D / Geometry_XY / Geometry_YZ ocultando las selections elegidas
    void exportGeometryPlots(String simulationRoot, java.util.List<Sel> hide) throws Exception {
        java.io.File root = new java.io.File(simulationRoot);
        if (!root.isDirectory() && !root.mkdirs()) throw new Exception("No se pudo crear " + simulationRoot);
        rmExport("img6");
        try { model.component("comp1").view().remove("view2"); } catch (Throwable t) { }

        model.component("comp1").view().create("view2", "geom1");
        model.component("comp1").view("view2").hideObjects().clear();
        model.component("comp1").view("view2").hideEntities().clear();
        for (int i = 0; i < hide.size(); i++) {
            String hideTag = "hide" + (i + 1);
            model.component("comp1").view("view2").hideEntities().create(hideTag);
            model.component("comp1").view("view2").hideEntities(hideTag).named(hide.get(i).tag);
        }

        model.result().export().create("img6", "Image");
        configureImage("img6", "off", true);
        model.result().export("img6").set("sourcetype", "geometry");
        model.result().export("img6").set("sourceobject", "geom1");
        model.result().export("img6").set("view", "view2");
        model.component("comp1").view("view2").camera().set("projection", "orthographic");

        model.component("comp1").view("view2").camera().set("orthoscale", 1.2);
        fitView("view2");
        model.result().export("img6").set("pngfilename", new java.io.File(root, "Geometry_3D.png").getPath());
        model.result().export("img6").run();

        model.component("comp1").view("view2").camera().set("up", new double[] {0, 1, 0});
        model.component("comp1").view("view2").camera().set("position", new double[] {0, 0, 1});
        model.component("comp1").view("view2").camera().set("orthoscale", 1.2);
        fitView("view2");
        model.result().export("img6").set("pngfilename", new java.io.File(root, "Geometry_XY.png").getPath());
        model.result().export("img6").run();

        model.component("comp1").view("view2").camera().set("position", new double[] {1, 0, 0});
        model.component("comp1").view("view2").camera().set("up", new double[] {0, 0, 1});
        model.component("comp1").view("view2").camera().set("orthoscale", 1.2);
        fitView("view2");
        model.result().export("img6").set("pngfilename", new java.io.File(root, "Geometry_YZ.png").getPath());
        model.result().export("img6").run();
    }
}

final Exporter exp = new Exporter();

// ----------------------------------------------------------------------------
// Parametric Sweep: deteccion, seleccion de valores y dataset temporal por valor
// ----------------------------------------------------------------------------
class Sweeper {
    // Solution dataset que alimenta al dataset (sigue la cadena "data" de los datasets derivados)
    String[] solutionOf(String dsTag) {
        String t = dsTag;
        for (int depth = 0; depth < 6 && !t.isEmpty() && u.datasetExists(t); depth++) {
            Object d = model.result().dataset(t);
            String s = u.str(u.call(d, "getString", "solution"));
            if (!s.isEmpty() && !s.equalsIgnoreCase("none")) return new String[] {s, depth > 0 ? "1" : "0"};
            String parent = u.str(u.call(d, "getString", "data"));
            if (parent.isEmpty() || parent.equalsIgnoreCase("none") || parent.equals(t)) break;
            t = parent;
        }
        return null;
    }

    // Estudio de la solucion; si no se puede leer, se busca por label (= shortLabel del dataset)
    String studyOf(String sol, String label) {
        String[] studies = model.study().tags();
        String std = u.str(u.call(model.sol(sol), "study"));
        if (!std.isEmpty() && u.has(studies, std)) return std;
        for (int i = 0; i < studies.length; i++) {
            if (model.study(studies[i]).label().trim().equalsIgnoreCase(label)) return studies[i];
        }
        return "";
    }

    String paramFeature(String std) {
        String[] ft = model.study(std).feature().tags();
        for (int i = 0; i < ft.length; i++) {
            String type = u.str(u.call(model.study(std).feature(ft[i]), "featureType"));
            if (type.equalsIgnoreCase("Parametric") || (type.isEmpty() && ft[i].startsWith("param"))) return ft[i];
        }
        return "";
    }

    // "1 1.05 range(1.1,0.05,1.3)" -> lista de valores; null si no es interpretable (unidades [..] ignoradas)
    java.util.List<Double> parseList(String expr) {
        if (expr == null) return null;
        String s = expr.replaceAll("\\[[^\\]]*\\]", "").trim();
        java.util.List<String> toks = new java.util.ArrayList<String>();
        StringBuilder cur = new StringBuilder();
        int depth = 0;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '(') depth++; else if (c == ')') depth--;
            if (depth == 0 && (Character.isWhitespace(c) || c == ',')) {
                if (cur.length() > 0) { toks.add(cur.toString()); cur.setLength(0); }
            } else cur.append(c);
        }
        if (cur.length() > 0) toks.add(cur.toString());

        java.util.List<Double> out = new java.util.ArrayList<Double>();
        for (int i = 0; i < toks.size(); i++) {
            String tok = toks.get(i);
            if (tok.startsWith("range(") && tok.endsWith(")")) {
                String[] a = tok.substring(6, tok.length() - 1).split(",");
                if (a.length < 2 || a.length > 3) return null;
                Double lo = u.num(a[0]), st = a.length == 3 ? u.num(a[1]) : Double.valueOf(1), hi = u.num(a[a.length - 1]);
                if (lo == null || st == null || hi == null || st.doubleValue() == 0) return null;
                int n = (int) Math.floor((hi.doubleValue() - lo.doubleValue()) / st.doubleValue() + 1e-9) + 1;
                if (n < 1 || n > 100000) return null;
                for (int k = 0; k < n; k++) out.add(Double.valueOf(lo.doubleValue() + k * st.doubleValue()));
            } else {
                Double v = u.num(tok);
                if (v == null) return null;
                out.add(v);
            }
        }
        return out;
    }

    // Respaldo cuando la lista del estudio no es numerica: valores reales de las outer solutions (un parametro)
    java.util.List<Double> pvals(String sol) {
        java.util.List<Double> out = new java.util.ArrayList<Double>();
        u.flatten(u.call(model.sol(sol), "getPVals"), out);
        return out.isEmpty() ? null : out;
    }

    // null si el dataset no depende de un Parametric Sweep con mas de un valor
    SweepInfo detect(Ds ds) {
        try {
            String[] so = solutionOf(ds.tag);
            if (so == null) return null;
            String std = studyOf(so[0], ds.shortLabel);
            if (std.isEmpty()) return null;
            String feat = paramFeature(std);
            if (feat.isEmpty()) return null;
            Object f = model.study(std).feature(feat);
            String[] names = u.strArr(u.call(f, "getStringArray", "pname"));
            String[] lists = u.strArr(u.call(f, "getStringArray", "plistarr"));
            if (names == null || names.length == 0) return null;

            SweepInfo si = new SweepInfo();
            si.study = std; si.solTag = so[0]; si.viaParent = "1".equals(so[1]); si.names = names;
            java.util.List<java.util.List<Double>> vals = new java.util.ArrayList<java.util.List<Double>>();
            boolean parsed = lists != null && lists.length >= names.length;
            for (int k = 0; parsed && k < names.length; k++) {
                java.util.List<Double> v = parseList(lists[k]);
                if (v == null || v.isEmpty()) parsed = false; else vals.add(v);
                if (lists[k].indexOf('[') >= 0) si.hasUnits = true;
            }
            if (!parsed) {
                vals.clear(); si.hasUnits = false;
                java.util.List<Double> pv = names.length == 1 ? pvals(so[0]) : null;
                if (pv == null) {
                    lg.log("WARN", ds.tag, "Parametric Sweep detectado en " + std + " pero no se pudieron leer sus valores; se procesa el dataset completo.");
                    return null;
                }
                vals.add(pv);
            }

            int m = names.length;
            if (m == 1) {
                for (int i = 0; i < vals.get(0).size(); i++) si.combos.add(new double[] {vals.get(0).get(i).doubleValue()});
            } else if (u.str(u.call(f, "getString", "sweeptype")).equalsIgnoreCase("sparse")) {
                int n = vals.get(0).size();
                for (int k = 1; k < m; k++) if (vals.get(k).size() != n) return null;
                for (int i = 0; i < n; i++) {
                    double[] c = new double[m];
                    for (int k = 0; k < m; k++) c[k] = vals.get(k).get(i).doubleValue();
                    si.combos.add(c);
                }
            } else {
                // All combinations: el primer parametro es el bucle externo
                int total = 1;
                for (int k = 0; k < m; k++) total *= vals.get(k).size();
                for (int i = 0; i < total; i++) {
                    double[] c = new double[m];
                    int rem = i;
                    for (int k = m - 1; k >= 0; k--) {
                        int sz = vals.get(k).size();
                        c[k] = vals.get(k).get(rem % sz).doubleValue();
                        rem /= sz;
                    }
                    si.combos.add(c);
                }
            }
            if (si.count() < 2) return null;
            for (int i = 0; i < si.count(); i++) {
                StringBuilder lb = new StringBuilder(), sf = new StringBuilder();
                for (int k = 0; k < m; k++) {
                    if (k > 0) { lb.append(", "); sf.append("_"); }
                    String tok = u.numTok(si.combos.get(i)[k]);
                    lb.append(names[k]).append(" = ").append(tok);
                    sf.append(u.safeName(names[k])).append("_").append(u.fsName(tok));
                }
                si.labels.add(lb.toString());
                si.suffixes.add(sf.toString());
            }
            return si;
        } catch (Throwable t) {
            lg.log("WARN", ds.tag, "No se pudo analizar el Parametric Sweep: " + t.getMessage());
            return null;
        }
    }

    // Pide al usuario los valores a analizar y genera un Ds independiente por valor (null si cancela)
    java.util.List<Ds> resolve(java.util.List<Ds> selected) {
        java.util.List<Ds> work = new java.util.ArrayList<Ds>();
        for (int i = 0; i < selected.size(); i++) {
            Ds ds = selected.get(i);
            SweepInfo si = detect(ds);
            if (si == null) { work.add(ds); continue; }
            lg.log("INFO", ds.tag, "Parametric Sweep detectado en \"" + ds.shortLabel + "\": " + si.count() + " valores.");
            java.util.List<Integer> pick = ui.askSweep(ds, si);
            if (pick == null) return null;
            for (int k = 0; k < pick.size(); k++) {
                int ix = pick.get(k).intValue();
                Ds d = new Ds();
                d.tag = ds.tag; d.srcTag = ds.tag;
                d.label = ds.label + " [" + si.labels.get(ix) + "]";
                d.shortLabel = ds.shortLabel + "_" + si.suffixes.get(ix);
                d.folderName = u.safeName(ds.shortLabel) + "_" + si.suffixes.get(ix);
                d.sweepIdx = ix + 1; d.sweep = si;
                work.add(d);
            }
        }
        return work;
    }

    // Intenta una forma de fijar la outer solution; "" si COMSOL la acepta, si no el mensaje de error
    String tryStrategy(String tag, int s, int idx, boolean viaParent) {
        try {
            if (viaParent) { try { model.result().dataset(tag).set("solutionparams", "manual"); } catch (Throwable t) { } }
            switch (s) {
                case 0:
                    model.result().dataset(tag).set("outersolnum", "manual");
                    model.result().dataset(tag).set("outersolnumindices", new int[] {idx});
                    break;
                case 1:
                    model.result().dataset(tag).set("outersolnum", String.valueOf(idx));
                    break;
                case 2:
                    model.result().dataset(tag).set("outersolnum", idx);
                    break;
                case 3:
                    u.call(model.result().dataset(tag), "setIndex", "looplevelinput", "manual", Integer.valueOf(0));
                    if (!u.lastErr.isEmpty()) return u.lastErr;
                    u.call(model.result().dataset(tag), "setIndex", "looplevel", new int[] {idx}, Integer.valueOf(0));
                    if (!u.lastErr.isEmpty()) return u.lastErr;
                    break;
                case 4:
                    model.result().dataset(tag).set("solnum", "manual");
                    model.result().dataset(tag).set("solnumindices", new int[] {idx});
                    break;
                default:
                    model.result().dataset(tag).set("solnum", String.valueOf(idx));
                    break;
            }
            return "";
        } catch (Throwable t) {
            return String.valueOf(t.getMessage());
        }
    }

    // Intenta fijar la outer solution en el propio dataset; false si el dataset no lo permite
    boolean applyOuter(String tag, Ds ds) {
        SweepInfo si = ds.sweep;
        int idx = ds.sweepIdx;
        for (int s = 0; s < 6; s++) {
            if (s == 3 && si.names.length != 1) continue;
            if (!tryStrategy(tag, s, idx, si.viaParent).isEmpty()) continue;
            if (si.hasUnits) return true;
            String v = verify(tag, si, idx - 1, 0);
            if (v == null || v.isEmpty()) return true;
        }
        return false;
    }

    // "" = coincide; texto = discrepancia; null = no concluyente. loop > 0: looplevel manual en la evaluacion
    String verify(String dsTag, SweepInfo si, int idx, int loop) {
        String ev = "ev_sweep_" + dsTag;
        try { model.result().numerical().remove(ev); } catch (Throwable t) { }
        try {
            model.result().numerical().create(ev, "EvalGlobal");
            model.result().numerical(ev).set("data", dsTag);
            if (loop > 0) {
                try {
                    model.result().numerical(ev).setIndex("looplevelinput", "manual", 0);
                    model.result().numerical(ev).setIndex("looplevel", String.valueOf(loop), 0);
                } catch (Throwable t) {
                    model.result().numerical(ev).set("looplevelinput", new String[] {"manual"});
                    model.result().numerical(ev).set("looplevel", new int[] {loop});
                }
            }
            boolean conclusive = true;
            for (int k = 0; k < si.names.length; k++) {
                model.result().numerical(ev).set("expr", new String[] {si.names[k]});
                java.util.List<Double> got = new java.util.ArrayList<Double>();
                u.flatten(u.call(model.result().numerical(ev), "getReal"), got);
                if (got.isEmpty()) return null;
                double want = si.combos.get(idx)[k];
                double tol = 1e-6 * Math.max(1, Math.abs(want));
                boolean found = false, other = false;
                for (int i = 0; i < got.size(); i++) {
                    if (Math.abs(got.get(i).doubleValue() - want) <= tol) found = true; else other = true;
                }
                if (!found) return si.names[k] + ": esperado " + u.numTok(want) + ", COMSOL devuelve " + u.numTok(got.get(0).doubleValue());
                if (other) conclusive = false;
            }
            return conclusive ? "" : null;
        } catch (Throwable t) {
            return null;
        } finally {
            try { model.result().numerical().remove(ev); } catch (Throwable t) { }
        }
    }

    // Otro dataset de la misma solucion/estudio que si exponga el barrido (p.ej. "Parametric Solutions")
    java.util.List<String> sweepAwareDatasets(Ds ds) {
        java.util.List<String> out = new java.util.ArrayList<String>();
        String[] tags = model.result().dataset().tags();
        for (int i = 0; i < tags.length; i++) {
            if (tags[i].equals(ds.srcTag)) continue;
            String pl = exp.propList(model.result().dataset(tags[i]));
            if (pl.indexOf("outersolnum") < 0 && pl.indexOf("solnum") < 0) continue;
            String[] so = solutionOf(tags[i]);
            if (so == null) continue;
            if (so[0].equals(ds.sweep.solTag) || studyOf(so[0], "").equals(ds.sweep.study)) out.add(tags[i]);
        }
        return out;
    }

    // Selecciona el valor del barrido: en el dataset si lo permite; si no, en un dataset hermano que si lo
    // permita; y como ultimo recurso via "looplevel" en cada plot group / export (exp.loop)
    void prepare(Ds ds) throws Exception {
        exp.loop = 0;
        String tmp = "dsweep_" + ds.srcTag + "_" + ds.sweepIdx;
        exp.rmDataset(tmp);
        model.result().dataset().duplicate(tmp, ds.srcTag);
        if (applyOuter(tmp, ds)) { ds.tag = tmp; return; }
        exp.rmDataset(tmp);

        java.util.List<String> sib = sweepAwareDatasets(ds);
        for (int i = 0; i < sib.size(); i++) {
            model.result().dataset().duplicate(tmp, sib.get(i));
            if (applyOuter(tmp, ds)) {
                lg.log("INFO", ds.srcTag, "Valor del barrido seleccionado a traves del dataset " + sib.get(i) + ".");
                ds.tag = tmp;
                return;
            }
            exp.rmDataset(tmp);
        }

        exp.loop = ds.sweepIdx;
        lg.log("INFO", ds.srcTag, "El dataset no expone la outer solution; se selecciona el valor con looplevel en los plots/exports.");
        if (!ds.sweep.hasUnits) {
            String v = verify(ds.srcTag, ds.sweep, ds.sweepIdx - 1, ds.sweepIdx);
            if (v == null) lg.log("WARN", ds.srcTag, "No se pudo comprobar el valor del barrido (" + ds.sweep.labels.get(ds.sweepIdx - 1) + "); revisa los resultados.");
            else if (!v.isEmpty()) throw new Exception("looplevel " + ds.sweepIdx + " no corresponde al valor esperado (" + v + ").");
        }
    }

    void release(Ds ds) {
        exp.loop = 0;
        if (ds.sweepIdx > 0 && !ds.tag.equals(ds.srcTag)) {
            exp.rmDataset(ds.tag);
            ds.tag = ds.srcTag;
        }
    }
}

final Sweeper sw = new Sweeper();

// ----------------------------------------------------------------------------
// Postproceso Python (histogramas): equivalente a run_*_python_postprocess
// ----------------------------------------------------------------------------
class Py {
    String scriptDir = "";

    void run(String script, String txtPath, String outPng, String inFlag, String outFlag,
             java.util.List<String> extra) throws Exception {
        java.io.File scriptFile = new java.io.File(scriptDir, script);
        if (!scriptFile.isFile()) throw new Exception("No se encontro el script Python: " + scriptFile);

        // En Windows se usan rutas temporales cortas para evitar MAX_PATH
        boolean win = System.getProperty("os.name", "").toLowerCase().contains("win");
        java.io.File tmpDir = null;
        String in = txtPath, out = outPng;
        if (win) {
            tmpDir = java.nio.file.Files.createTempDirectory("comsol_py_").toFile();
            in = new java.io.File(tmpDir, "input.txt").getPath();
            out = new java.io.File(tmpDir, "output.png").getPath();
            java.nio.file.Files.copy(java.nio.file.Paths.get(txtPath), java.nio.file.Paths.get(in),
                java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        }
        try {
            String[][] candidates = {{"python"}, {"python3"}, {"py", "-3"}, {"py"}};
            StringBuilder errors = new StringBuilder();
            for (int i = 0; i < candidates.length; i++) {
                java.util.List<String> cmd = new java.util.ArrayList<String>();
                for (int k = 0; k < candidates[i].length; k++) cmd.add(candidates[i][k]);
                cmd.add(scriptFile.getPath());
                cmd.add(inFlag); cmd.add(in);
                cmd.add(outFlag); cmd.add(out);
                cmd.addAll(extra);
                cmd.add("--no-show");
                String output;
                int status;
                try {
                    ProcessBuilder pb = new ProcessBuilder(cmd);
                    pb.redirectErrorStream(true);
                    Process pr = pb.start();
                    java.io.InputStream is = pr.getInputStream();
                    java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
                    byte[] buf = new byte[4096];
                    int n;
                    while ((n = is.read(buf)) > 0) bos.write(buf, 0, n);
                    status = pr.waitFor();
                    output = bos.toString();
                } catch (SecurityException e) {
                    // COMSOL bloquea la ejecucion de procesos: no tiene sentido probar mas interpretes
                    String bat = writeBatch(scriptFile, txtPath, outPng, inFlag, outFlag, extra);
                    throw new Exception("COMSOL no permite ejecutar procesos externos (Preferences > Security > "
                        + "Methods and Libraries: permitir llamadas al sistema / acceso a ficheros). "
                        + (bat.isEmpty() ? "" : "Comando guardado en: " + bat + " (ejecutalo manualmente).")
                        + " Detalle: " + e.getMessage());
                } catch (Exception e) {
                    errors.append(candidates[i][0]).append(": ").append(e.getMessage()).append(" | ");
                    continue;
                }
                if (status == 0) {
                    if (!out.equals(outPng)) {
                        java.nio.file.Files.copy(java.nio.file.Paths.get(out), java.nio.file.Paths.get(outPng),
                            java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                    }
                    return;
                }
                String o = output.trim().replace("\n", " | ");
                errors.append(candidates[i][0]).append(": ").append(o.length() > 350 ? o.substring(0, 350) + " ..." : o).append(" | ");
            }
            throw new Exception("Fallo el postproceso Python (" + script + "). Instala numpy y matplotlib. " + errors);
        } finally {
            if (tmpDir != null) u.deleteTree(tmpDir);
        }
    }

    String q(String s) { return "\"" + s.replace("\"", "\"\"") + "\""; }

    // Anade el comando a run_python_postprocess.bat (junto al .txt) para lanzarlo fuera de COMSOL
    String writeBatch(java.io.File scriptFile, String txtPath, String outPng, String inFlag, String outFlag,
                      java.util.List<String> extra) {
        try {
            java.io.File dir = new java.io.File(txtPath).getParentFile();
            java.io.File bat = new java.io.File(dir, "run_python_postprocess.bat");
            boolean isNew = !bat.exists();
            StringBuilder sb = new StringBuilder();
            if (isNew) sb.append("@echo off\r\n");
            sb.append("python ").append(q(scriptFile.getPath()))
              .append(" ").append(inFlag).append(" ").append(q(txtPath))
              .append(" ").append(outFlag).append(" ").append(q(outPng));
            for (int i = 0; i < extra.size(); i++) sb.append(" ").append(q(extra.get(i)));
            sb.append(" --no-show\r\n");
            java.io.FileWriter fw = new java.io.FileWriter(bat, true);
            try { fw.write(sb.toString()); } finally { fw.close(); }
            return bat.getPath();
        } catch (Exception ex) {
            return "";
        }
    }

    String base(String txtPath) { return txtPath.replaceAll("\\.[^.\\\\/]*$", ""); }

    void bfov(String txtPath, String modelName, String fovInfo, String analysis, String field) throws Exception {
        java.util.List<String> a = new java.util.ArrayList<String>();
        a.add("--magnet-info"); a.add(modelName);
        a.add("--fov-info"); a.add(fovInfo);
        a.add("--analysis"); a.add(analysis);
        a.add("--field-label"); a.add(field);
        a.add("--bfov-only");
        run("Comsol_extracted_histograms_BFOV_Magnets.py", txtPath, base(txtPath) + ".png", "--file-path", "--output-png", a);
    }

    void magnetsNormM(String txtPath, String modelName, String analysis, double br, double step) throws Exception {
        java.util.List<String> a = new java.util.ArrayList<String>();
        a.add("--magnet-info"); a.add(modelName);
        a.add("--analysis"); a.add(analysis);
        a.add("--br"); a.add(u.fmt(br));
        a.add("--step-percent"); a.add(u.fmt(step));
        run("Comsol_extracted_magnets_histogram.py", txtPath, base(txtPath) + ".png", "--file-path-m", "--output-png-m", a);
    }

    void magnetsNormH(String txtPath, MagCfg m) throws Exception {
        java.util.List<String> a = new java.util.ArrayList<String>();
        a.add("--Hlinear_end"); a.add(u.fmt(m.hlinearEnd));
        a.add("--Hknee"); a.add(u.fmt(m.hknee));
        a.add("--Hcb"); a.add(u.fmt(m.hcb));
        a.add("--Hcj"); a.add(u.fmt(m.hcj));
        for (int i = 0; i < m.extra.size(); i++) { a.add("--extra"); a.add(m.extra.get(i).name + "=" + u.fmt(m.extra.get(i).value)); }
        run("Histogram_H_Postprocess.py", txtPath, base(txtPath) + "_Hfield.png", "--file-path", "--output-png", a);
    }
}

final Py py = new Py();

// ----------------------------------------------------------------------------
// Orquestacion (extraction_controller + run_bfov_exports + run_magnets_exports)
// ----------------------------------------------------------------------------
class Runner {
    void bfov(Ds ds, String folder, Opts o, Sel dom) throws Exception {
        String safeDs = u.safeName(ds.shortLabel);
        String histTxt = new java.io.File(folder, "BFOV_histogram_" + safeDs + "_" + o.modelName + ".txt").getPath();
        String png3d = new java.io.File(folder, "BFOV_" + safeDs + "_" + o.modelName + ".png").getPath();
        String selTag = "", selLabel = "", fovInfo = o.fovInfo, analysis = ds.shortLabel, coordBase = "", prefix = "B_FOV";

        if (dom != null) {
            selTag = dom.tag; selLabel = dom.label;
            String safeSel = u.safeName(selLabel);
            if (safeSel.isEmpty()) safeSel = u.safeName(selTag);
            histTxt = new java.io.File(folder, "B_" + safeSel + "_Histogram_" + o.modelName + ".txt").getPath();
            png3d = new java.io.File(folder, "B_" + safeSel + "_3DPlot_" + o.modelName + ".png").getPath();
            coordBase = "B_" + safeSel + "_CustomCoordinates_" + o.modelName;
            prefix = "B_" + selLabel;
            fovInfo = selLabel; analysis = selLabel;
        }

        if (o.bfov3d || o.bfovHist) {
            exp.exportDataset(ds.tag, histTxt, png3d, selTag, selLabel, o.histBins, o.changeOrtho ? o.orthoScale : -1, o.field);
            lg.log("INFO", ds.tag, prefix + ": 3D plot + histograma exportados.");
        }

        if (o.bfovHist && o.runPython) {
            try {
                py.bfov(histTxt, o.modelName, fovInfo, analysis, o.field);
                lg.log("INFO", ds.tag, "Postproceso BFOV Python completado.");
            } catch (Exception e) {
                lg.log("WARN", ds.tag, "Postproceso BFOV no ejecutado: " + e.getMessage());
            }
        }

        if (o.bfovCoord) {
            CoordCfg c = o.coord;
            c.outputBaseName = coordBase;
            lg.log("INFO", ds.tag, "Iniciando exportacion " + prefix + " Custom Coordinates ("
                + (c.fromFile ? "From file: " + new java.io.File(c.filePath).getName() : "nTheta=" + c.nTheta + ", nPhi=" + c.nPhi + ", R=" + c.R + " m")
                + ", puntos=" + c.coords.length + ")...");
            String out = exp.exportCustomCoordinates(ds.tag, folder, c, selTag);
            lg.log("INFO", ds.tag, prefix + " Custom Coordinates exportado: " + out + " (sin PNG de preview)");
        }
    }

    void magnets(Ds ds, String folder, Opts o) throws Exception {
        String safe = u.safeName(ds.shortLabel);
        if (safe.isEmpty()) safe = u.safeName(ds.tag);
        String suffix = safe + "_" + o.modelName;
        String png3d = new java.io.File(folder, "Magnets_" + suffix + ".png").getPath();
        String txt3d = new java.io.File(folder, "Magnets_" + suffix + ".txt").getPath();
        String histTxt = new java.io.File(folder, "Magnets_histogram_" + suffix + ".txt").getPath();
        String histPng = new java.io.File(folder, "Magnets_histogram_" + suffix + ".png").getPath();
        String hTxt = new java.io.File(folder, "Magnets_histogram_normH_" + suffix + ".txt").getPath();
        String hPng = new java.io.File(folder, "Magnets_histogram_normH_" + suffix + ".png").getPath();

        if (o.magnets3d) {
            lg.log("INFO", ds.tag, "Iniciando exportacion Magnets 3D Plot...");
            try {
                exp.exportMagnets3d(ds.tag, png3d, txt3d);
                lg.log("INFO", ds.tag, "Magnets 3D Plot exportado (PNG y TXT).");
            } catch (Exception e) {
                lg.log("WARN", ds.tag, "Magnets 3D Plot no se pudo exportar: " + e.getMessage());
            }
        }

        if (o.magnetsHist) {
            MagCfg m = o.mag;
            lg.log("INFO", ds.tag, "Iniciando exportacion Magnets Histogram (bins=" + m.bins + ")...");
            try {
                if (m.normM) {
                    exp.exportMagnetsHistogram(ds.tag, histTxt, histPng, m.bins, "mu0_const*mfnc.normM", "T");
                    lg.log("INFO", ds.tag, "Magnets Histogram normM exportado (bins=" + m.bins + ").");
                    if (o.runPython) {
                        try {
                            py.magnetsNormM(histTxt, o.modelName, ds.shortLabel, m.br, m.step);
                            lg.log("INFO", ds.tag, "Postproceso Magnets Python completado (Br=" + m.br + " T, step=" + m.step + "%).");
                        } catch (Exception e) {
                            lg.log("WARN", ds.tag, "Postproceso Magnets no ejecutado: " + e.getMessage());
                        }
                    }
                }
                if (m.normH) {
                    exp.exportMagnetsHistogram(ds.tag, hTxt, hPng, m.bins, "mfnc.normH", "kA/m");
                    lg.log("INFO", ds.tag, "Magnets Histogram normH exportado (bins=" + m.bins + ").");
                    if (o.runPython) {
                        try {
                            py.magnetsNormH(hTxt, m);
                            lg.log("INFO", ds.tag, "Postproceso Magnets normH Python completado.");
                        } catch (Exception e) {
                            lg.log("WARN", ds.tag, "Postproceso Magnets normH no ejecutado: " + e.getMessage());
                        }
                    }
                }
            } catch (Exception e) {
                lg.log("WARN", ds.tag, "Magnets Histogram no se pudo exportar: " + e.getMessage());
            }
        }
    }

    void extract(Opts o, java.util.List<Ds> datasets) {
        long t0 = System.currentTimeMillis();
        int nOk = 0, nErr = 0;
        lg.log("INFO", "", "Iniciando extraccion de " + datasets.size() + " dataset(s)"
            + (o.domainMode ? " en " + o.domains.size() + " seleccion(es) de dominio." : "."));
        for (int i = 0; i < datasets.size(); i++) {
            Ds ds = datasets.get(i);
            try {
                lg.log("INFO", ds.tag, "Preparando dataset " + (i + 1) + " de " + datasets.size() + ": " + ds.shortLabel);
                if (ds.sweepIdx > 0) {
                    sw.prepare(ds);
                    lg.log("INFO", ds.srcTag, "Parametric Sweep: " + ds.sweep.labels.get(ds.sweepIdx - 1) + " (outer solution " + ds.sweepIdx + ").");
                }
                String folder = u.createOutputFolder(o.outDir, ds.folderName.isEmpty() ? u.safeName(ds.shortLabel) : ds.folderName, ds.tag);
                lg.log("INFO", ds.tag, "Carpeta de salida lista: " + folder);
                if (o.domainMode) {
                    for (int k = 0; k < o.domains.size(); k++) bfov(ds, folder, o, o.domains.get(k));
                } else {
                    bfov(ds, folder, o, null);
                }
                if (o.magnets3d || o.magnetsHist) magnets(ds, folder, o);
                nOk++;
                lg.log("INFO", ds.tag, "OK -> " + folder);
            } catch (Throwable e) {
                nErr++;
                lg.log("ERROR", ds.tag, String.valueOf(e.getMessage()));
            } finally {
                sw.release(ds);
            }
            lg.log("INFO", "", "Progreso: " + (i + 1) + " / " + datasets.size() + " datasets procesados.");
        }
        lg.log("INFO", "", "--- Resumen de extraccion ---");
        lg.log("INFO", "", "  Datasets OK:    " + nOk);
        lg.log("INFO", "", "  Datasets error: " + nErr);
        lg.log("INFO", "", "  Directorio:     " + new java.io.File(o.outDir, "Simulation_results").getPath());
        lg.log("INFO", "", "  Tiempo total:   " + (System.currentTimeMillis() - t0) / 1000 + " s");
    }
}

// ----------------------------------------------------------------------------
// Flujo principal
// ----------------------------------------------------------------------------
try {
    int action = ui.choose("COMSOL Analyzer", "Selecciona la accion a ejecutar:",
        new String[] {"Run Extraction", "Extract Geometry Plots", "Cancel"});
    if (action == 0 || action == 1) {
        Opts o = new Opts();
        // Por defecto, la carpeta del .mph actual (modificable); si no esta guardado, la ultima usada
        String modelDir = u.modelDir();
        o.outDir = modelDir.isEmpty() ? prefs.s("LastOutputDir", "") : modelDir;
        String nm = "";
        try { nm = model.label(); } catch (Throwable t) { }
        o.modelName = u.safeName(nm == null ? "" : nm.replaceAll("(?i)\\.mph$", ""));
        o.scriptDir = prefs.s("ScriptDir", DEFAULT_SCRIPT_DIR);
        o.orthoScale = prefs.d("ProjectionOrthoScale", 0.35);
        o.histBins = (int) prefs.d("HistogramBins", 100);

        if (action == 1) {
            // ---- Extract Geometry Plots ----
            String dir = ui.chooseDir(o.outDir);
            if (dir != null) {
                String w = u.checkWritable(dir);
                if (!w.isEmpty()) {
                    ui.error("Output dir", w);
                } else {
                    prefs.put("LastOutputDir", dir);
                    java.util.List<Sel> hide = new java.util.ArrayList<Sel>();
                    if (ui.askHideSelections(hide)) {
                        String root = new java.io.File(dir, "Simulation_results").getPath();
                        long t0 = System.currentTimeMillis();
                        lg.log("INFO", "", "Iniciando export de Geometry plots.");
                        exp.exportGeometryPlots(root, hide);
                        lg.log("INFO", "", "--- Resumen Geometry plots ---");
                        lg.log("INFO", "", "  Directorio:   " + root);
                        lg.log("INFO", "", "  Tiempo total: " + (System.currentTimeMillis() - t0) / 1000 + " s");
                        ui.info("Geometry plots", ui.scroll(new javax.swing.JTextArea(lg.sb.toString(), 12, 70), 640, 260));
                    }
                }
            }
        } else {
            // ---- Run Extraction ----
            java.util.List<Ds> all = u.datasets();
            java.util.List<Ds> selected = new java.util.ArrayList<Ds>();
            boolean go = !all.isEmpty();
            if (all.isEmpty()) ui.error("Datasets", "El modelo no contiene datasets.");

            // Modelo sin guardar: se pide la carpeta de salida al inicio
            if (go && modelDir.isEmpty()) {
                String d = ui.chooseDir(o.outDir);
                if (d != null) o.outDir = d;
            }
            go = go && ui.askMain(o, all, selected);
            if (go) {
                prefs.put("LastOutputDir", o.outDir);
                prefs.put("ScriptDir", o.scriptDir);
                py.scriptDir = o.scriptDir;
                o.coord = new CoordCfg();
                o.mag = new MagCfg();
                o.orthoScale = prefs.d("ProjectionOrthoScale", 0.35);
            }
            if (go && o.changeFov) go = ui.askDomains(o);
            if (go && !o.bfov3d && !o.bfovHist && !o.bfovCoord && !o.magnets3d && !o.magnetsHist) {
                ui.error("Salida requerida", "Debe seleccionar al menos una opcion de salida.");
                go = false;
            }
            if (go) {
                java.util.List<Ds> work = sw.resolve(selected);
                if (work == null) go = false; else selected = work;
            }
            if (go && o.bfov3d && o.changeOrtho) go = ui.askOrthoScale(o);
            if (go && o.bfovHist) go = ui.askHistBins(o);
            if (go && o.bfovCoord) go = ui.askCoordinates(o);
            if (go && o.magnetsHist) go = ui.askMagnets(o);
            if (go) {
                new Runner().extract(o, selected);
                ui.info("Resumen de extraccion", ui.scroll(new javax.swing.JTextArea(lg.sb.toString(), 16, 90), 760, 340));
            } else {
                lg.log("INFO", "", "Extraccion cancelada por el usuario.");
            }
        }
    }
} catch (Throwable err) {
    lg.log("ERROR", "", "Error inesperado: " + err);
    ui.error("COMSOL Analyzer - Error", String.valueOf(err.getMessage()));
}
