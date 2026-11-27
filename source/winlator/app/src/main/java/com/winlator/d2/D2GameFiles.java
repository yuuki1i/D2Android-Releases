package com.winlator.d2;

import android.content.Context;
import java.io.File;
import java.io.InputStream;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Tells from the hashes whether a game folder really is one consistent 1.13c or
 * 1.13d install. A folder that mixes both looks fine to the version check (it
 * reads Game.exe only) but drives PlugY into the wrong offset table, which is
 * what "BYTE xx wanted but yy found" reports.
 */
final class D2GameFiles {
    private static final String[] NAMES = {
        "Storm.dll", "D2Client.dll", "D2Common.dll", "D2Game.dll", "D2gfx.dll", "D2Launch.dll", "D2Win.dll"
    };

    private D2GameFiles() {}

    static String summary(Context context, File dir) {
        Map<String, String> c = load(context, "checksums-113c.txt");
        Map<String, String> d = load(context, "checksums-113d.txt");
        StringBuilder out = new StringBuilder();
        int c13c = 0, c13d = 0, other = 0;
        for (String name : NAMES) {
            File file = find(dir, name);
            if (file == null) {
                out.append(name).append("=missing ");
                other++;
                continue;
            }
            String hash;
            try {
                hash = GameVersion.sha256(file);
            }
            catch (Exception e) {
                out.append(name).append("=unreadable ");
                other++;
                continue;
            }
            String wantC = c.get(name.toLowerCase(Locale.ROOT));
            String wantD = d.get(name.toLowerCase(Locale.ROOT));
            if (wantC != null && wantC.equalsIgnoreCase(hash)) {
                out.append(name).append("=1.13c ");
                c13c++;
            }
            else if (wantD != null && wantD.equalsIgnoreCase(hash)) {
                out.append(name).append("=1.13d ");
                c13d++;
            }
            else {
                out.append(name).append("=other ");
                other++;
            }
        }
        String verdict;
        if (c13c == NAMES.length) verdict = "consistent 1.13c";
        else if (c13d == NAMES.length) verdict = "consistent 1.13d";
        else verdict = "MIXED: " + c13c + " x 1.13c against " + c13d + " x 1.13d (PlugY takes the wrong offset table)";
        return verdict + " | " + out.toString().trim();
    }

    private static File find(File dir, String name) {
        if (dir == null) return null;
        File file = new File(dir, name);
        if (file.isFile()) return file;
        file = new File(dir, name.toLowerCase(Locale.ROOT));
        return file.isFile() ? file : null;
    }

    private static Map<String, String> load(Context context, String asset) {
        Map<String, String> out = new LinkedHashMap<>();
        try (InputStream in = context.getAssets().open(asset)) {
            for (Map.Entry<String, String> e : GameVersion.parseList(in).entrySet())
                out.put(e.getKey().toLowerCase(Locale.ROOT), e.getValue());
        }
        catch (Exception e) {
            D2Trace.log("checksums " + asset + " not readable: " + e);
        }
        return out;
    }
}
