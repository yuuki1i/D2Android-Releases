package com.winlator.d2;

import android.content.Context;

import com.winlator.R;
import com.winlator.core.FileUtils;

import java.io.File;
import java.io.IOException;
import java.util.Locale;









public final class GameShadow {

    public static final String RENDERER_D2GL = "d2gl";
    public static final String RENDERER_D2DX = "d2dx";
    private static final String DIR_NAME = "D2Android-Game";
    private static final String D2DX_ASSET = "d2/d2dx/glide3x.dll";

    private static final String MOD_ASSET_DIR = "d2/mod/";
    public static final String LOADER_EXE = "D2Android.exe";
    private static final String MOD_DLL = "d2android-mod.dll";
    /** 1.13c build of the same touch layer; installed under MOD_DLL so the loader stays version agnostic. */
    private static final String MOD_DLL_113C = "d2android-mod-113c.dll";

    private GameShadow() {}


    static String d2dxAsset(int atlasLayers) {
        return atlasLayers >= 2048 ? D2DX_ASSET : "d2/d2dx/glide3x-atlas" + atlasLayers + ".dll";
    }


    static File dir(Context context) {
        return new File(D2Runtime.driveC(context), DIR_NAME);
    }

    public static boolean isD2DXBundled(Context context) {
        try (java.io.InputStream ignored = context.getAssets().open(D2DX_ASSET)) {
            return true;
        }
        catch (IOException e) {
            return false;
        }
    }

    public static boolean isModBundled(Context context) {
        try (java.io.InputStream ignored = context.getAssets().open(MOD_ASSET_DIR + LOADER_EXE)) {
            return true;
        }
        catch (IOException e) {
            return false;
        }
    }






    static void plugyStatsHint(Context context, File strings) {
        if (!strings.isFile()) return;
        try {
            byte[] file = java.nio.file.Files.readAllBytes(strings.toPath());
            byte[] out = D2PlugYTexts.statsHint(file, textIn(context, java.util.Locale.GERMAN, R.string.plugy_stats_plus_hint),
                textIn(context, java.util.Locale.ENGLISH, R.string.plugy_stats_plus_hint));
            if (out != null) java.nio.file.Files.write(strings.toPath(), out);
        }
        catch (IOException e) {
            android.util.Log.w("D2PlugY", "PlugY's strings not changed", e);
        }
    }


    private static String textIn(Context context, java.util.Locale locale, int id) {
        android.content.res.Configuration config = new android.content.res.Configuration(context.getResources().getConfiguration());
        config.setLocale(locale);
        return context.createConfigurationContext(config).getString(id);
    }





    public static File prepare(Context context, File driveC, File gameDir, String d2dxCfg) throws IOException {
        return prepare(context, driveC, gameDir, d2dxCfg, D2Mods.active(context), true);
    }

    public static File prepare(Context context, File driveC, File gameDir, String d2dxCfg, D2ModInfo.Mod mod) throws IOException {
        return prepare(context, driveC, gameDir, d2dxCfg, mod, true);
    }

    public static File prepare(Context context, File driveC, File gameDir, String d2dxCfg, D2ModInfo.Mod mod, boolean useD2DX) throws IOException {


        File saveDir = mod != null ? mod.saves() : D2Saves.saveDir(gameDir);
        if (!D2Saves.recover(saveDir)) {
            throw new IOException(D2Text.get(context, R.string.saves_error_import_unfinished));
        }


        D2SaveRepair.run(saveDir);
        File shadowDir = new File(driveC, DIR_NAME);
        if (!shadowDir.isDirectory() && !shadowDir.mkdirs()) throw new IOException("Cannot create " + shadowDir);


        File[] existing = shadowDir.listFiles();
        if (existing != null) {
            for (File file : existing) if (FileUtils.isSymlink(file)) file.delete();
        }

        D2ModOverlay.clear(shadowDir, (id) -> D2ModInfo.validId(id) && new File(D2Mods.root(), id).isDirectory()
            ? new File(new File(D2Mods.root(), id), D2ModInfo.CACHE) : null);

        File glide = new File(shadowDir, "glide3x.dll");

        int ingame = D2IngameResolution.read(shadowDir);

        if (useD2DX) {
            FileUtils.copy(context, D2Settings.vortek(context)
                ? d2dxAsset(D2GpuPath.tier(D2Runtime.totalMem(context)).atlasLayers) : D2DX_ASSET, glide);
            if (!glide.isFile()) throw new IOException("D2DX is not bundled in this app version");
            if (ingame != D2IngameResolution.MODE_WIDE) D2Trace.log(D2IngameResolution.apply(glide, ingame));
        }
        else {
            if (glide.exists() && !glide.delete()) D2Trace.log("could not remove stale D2DX glide3x.dll");
            D2Trace.log("D2DX disabled; launch using Diablo II DirectDraw path");
        }


        boolean modBundled = isModBundled(context);
        String dll = modBundled ? modDll(context, gameDir) : MOD_DLL;
        if (modBundled) {
            FileUtils.copy(context, MOD_ASSET_DIR + LOADER_EXE, new File(shadowDir, LOADER_EXE));
            FileUtils.copy(context, MOD_ASSET_DIR + dll, new File(shadowDir, MOD_DLL));
        }

        D2PlugY.setCowPortalSupported(modBundled && !MOD_DLL_113C.equals(dll));
        boolean plugy = modBundled && D2Settings.modEnabled(context) && D2Settings.plugy(context);
        D2PlugY.install(context, shadowDir, saveDir, plugy, gameDir);
        if (plugy) plugyStatsHint(context, new File(new File(shadowDir, "PlugY"), D2PlugYTexts.STRINGS_FILE));


        if (useD2DX) FileUtils.writeString(new File(shadowDir, "d2dx.cfg"), d2dxCfg != null ? d2dxCfg : defaultD2DXConfig());


        java.util.List<String> laid = mod == null ? java.util.Collections.emptyList()
            : D2ModOverlay.lay(shadowDir, mod.files(), gameDir, mod.cache(), mod.id, GameShadow::isProvided);
        if (mod != null) D2Trace.log("mod " + mod.id + " laid over the game folder: " + laid);
        File[] entries = gameDir.listFiles();
        if (entries == null) throw new IOException("Spielordner nicht lesbar: " + gameDir);
        for (File entry : entries) {
            String name = entry.getName();
            if (isProvided(name)) continue;
            if (D2ModOverlay.nameIn(laid, name.toLowerCase(Locale.ROOT)) != null) continue;
            File link = new File(shadowDir, name);
            if (link.exists() || FileUtils.isSymlink(link)) continue;
            FileUtils.symlink(entry, link);
        }
        D2Trace.log("shadow: " + D2GameFiles.summary(context, shadowDir));
        return shadowDir;
    }





    /** 1.13c carries its own offset table, so its mod build is installed under the 1.13d file name. */
    static String modDll(Context context, File gameDir) {
        if (!bundled(context, MOD_ASSET_DIR + MOD_DLL_113C)) return MOD_DLL;
        if (!"1.13c".equals(versionOf(gameDir))) return MOD_DLL;
        D2Trace.log("1.13c game folder detected; installing the 1.13c mod build");
        D2Trace.log("game files: " + D2GameFiles.summary(context, gameDir));
        return MOD_DLL_113C;
    }

    private static boolean bundled(Context context, String asset) {
        try (java.io.InputStream ignored = context.getAssets().open(asset)) {
            return true;
        }
        catch (IOException e) {
            return false;
        }
    }

    private static String versionOf(File gameDir) {
        for (String name : new String[] {"Game.exe", "game.exe"}) {
            File exe = new File(gameDir, name);
            if (!exe.isFile()) continue;
            try {
                return GameVersion.versionName(GameVersion.readVersion(exe));
            }
            catch (IOException e) {
                D2Trace.log("could not read the game version: " + e);
            }
        }
        return null;
    }

    private static boolean isProvided(String name) {
        String lower = name.toLowerCase(Locale.ROOT);
        return lower.equals("glide3x.dll") || lower.equals("d2dx.cfg") || lower.equals("ddraw.dll")
            || lower.startsWith("d2dx_sgd2freeres") || lower.startsWith("_d2test") || lower.startsWith("d2android")
            || lower.equals("plugy.dll") || lower.equals("plugy.ini") || lower.equals("plugy");
    }






    public static String defaultD2DXConfig() {
        return buildD2DXConfig(null, 0);
    }


    public static String buildD2DXConfig(String gameSize, int filtering) {
        String size = "[-1,-1]";
        if (gameSize != null) {
            String[] parts = gameSize.split("x");
            size = "[" + Integer.parseInt(parts[0]) + "," + Integer.parseInt(parts[1]) + "]";
        }
        return "# Written by D2Android (D2LaunchActivity)\r\n"
            + "[window]\r\nscale=1\r\nposition=[-1,-1]\r\nframeless=true\r\n\r\n"
            + "[game]\r\nsize=" + size + "\r\nfiltering=" + filtering + "\r\n\r\n"
            + "[optouts]\r\nnologo=true\r\nnocompatmodefix=true\r\n";
    }
}
