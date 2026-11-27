package com.winlator.d2;

import com.winlator.core.FileUtils;

import java.io.File;

/** Shows, on the phone, what the pack really consists of — no log reading needed. */
public final class D2PackCheck {

    private D2PackCheck() {}


    public static String report(File gameDir, File shadowDir) {
        StringBuilder b = new StringBuilder();
        b.append("GAME: ").append(gameDir).append('\n');
        String[] need = {"patchload.dll", "D2Ext.dll", "D2Ext.ini", "PlugY.ini", "PlugY.dll",
            "Plugin", "Plugin/d2hackmap.dll", "Plugin/_d2hackmap.dll", "Plugin/d2hackmap.cfg", "data"};
        for (String name : need) b.append(mark(new File(gameDir, name))).append(' ').append(name).append('\n');

        File ini = new File(gameDir, "PlugY.ini");
        if (ini.isFile()) {
            String text = FileUtils.readString(ini);
            b.append('\n').append(line(text, "DllToLoad")).append('\n').append(line(text, "DllToLoad2"));
            b.append('\n').append(line(text, "ActiveCheckMemory")).append('\n').append(line(text, "ActivePlugin"));
        }
        b.append("\nSHADOW: ").append(shadowDir).append('\n');
        for (String name : new String[]{"patchload.dll", "D2Ext.ini", "Plugin", "PlugY.ini"})
            b.append(mark(new File(shadowDir, name))).append(' ').append(name).append('\n');

        b.append("\nMOD: ").append(chain(new File(shadowDir, "d2android-mod.log")));
        return b.toString();
    }


    private static String mark(File f) {
        return f.isDirectory() ? "[dir]" : f.isFile() ? "[ok ]" : "[-- ]";
    }


    private static String line(String ini, String key) {
        String k = "\r\n" + key + "=";
        int at = ini.indexOf(k);
        if (at < 0) return key + " = (missing)";
        int end = ini.indexOf("\r\n", at + k.length());
        return key + " = " + ini.substring(at + k.length(), end < 0 ? ini.length() : end);
    }


    private static String chain(File log) {
        if (!log.isFile()) return "no mod log";
        String text = FileUtils.readString(log);
        int at = text.lastIndexOf("chain: ");
        if (at < 0) return "no chain line yet (game never reached the first frame)";
        int end = text.indexOf('\n', at);
        return text.substring(at, end < 0 ? text.length() : end).trim();
    }
}
