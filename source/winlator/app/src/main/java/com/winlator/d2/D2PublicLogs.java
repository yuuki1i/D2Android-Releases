package com.winlator.d2;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

final class D2PublicLogs {
    private static Uri sessionUri;
    private static File legacyFile;
    private static Context app;
    private static final Object LOCK = new Object();
    private D2PublicLogs() {}

    static void begin(Context context) {
        synchronized (LOCK) {
            app = context.getApplicationContext();
            sessionUri = null; legacyFile = null;
            String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.ROOT).format(new Date());
            String name = "D2Android-" + stamp + ".log";
            try {
                if (Build.VERSION.SDK_INT >= 29) {
                    ContentValues values = new ContentValues();
                    values.put(MediaStore.Downloads.DISPLAY_NAME, name);
                    values.put(MediaStore.Downloads.MIME_TYPE, "text/plain");
                    values.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/D2Android/logs/");
                    sessionUri = app.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                } else {
                    File dir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "D2Android/logs");
                    if (dir.mkdirs() || dir.isDirectory()) legacyFile = new File(dir, name);
                }
                writeLocked("=== D2Android session " + stamp + " ===\n");
                writeLocked("Android API: " + Build.VERSION.SDK_INT + " / " + Build.VERSION.RELEASE + "\n");
                writeLocked("Device: " + Build.MANUFACTURER + " " + Build.MODEL + "\n");
            } catch (Exception e) { android.util.Log.e("D2PublicLogs", "Cannot create Download log", e); }
        }
    }
    static void append(String text) {
        synchronized (LOCK) { writeLocked(text.endsWith("\n") ? text : text + "\n"); }
    }
    private static void writeLocked(String text) {
        try {
            if (sessionUri != null && app != null) {
                try (OutputStream out = app.getContentResolver().openOutputStream(sessionUri, "wa")) {
                    if (out != null) out.write(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                }
            } else if (legacyFile != null) {
                try (FileOutputStream out = new FileOutputStream(legacyFile, true)) {
                    out.write(text.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                }
            }
        } catch (Exception e) { android.util.Log.e("D2PublicLogs", "Cannot append Download log", e); }
    }
}
