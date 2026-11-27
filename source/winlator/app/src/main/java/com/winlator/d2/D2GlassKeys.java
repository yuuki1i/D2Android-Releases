package com.winlator.d2;

import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;

/**
 * The key bar at the top of the screen, drawn by the app instead of the game's stone pictures.
 *
 * The game's own frames come with the game font, which cannot show the app's labels (they turn
 * into question marks on a translated install) and cannot be restyled. This draws a glass panel
 * instead and offers three looks, so the whole bar can be swapped without touching the game.
 */
public final class D2GlassKeys {
    public static final int CLASSIC = 0, XBOX = 1, SWITCH = 2, PLAYSTATION = 3;

    private static final Paint body = new Paint(Paint.ANTI_ALIAS_FLAG);
    private static final Paint line = new Paint(Paint.ANTI_ALIAS_FLAG);
    private static final Paint glow = new Paint(Paint.ANTI_ALIAS_FLAG);
    private static final RectF tmp = new RectF();

    private D2GlassKeys() {}

    public static String name(int theme) {
        switch (theme) {
            case XBOX: return "Xbox";
            case SWITCH: return "Switch";
            case PLAYSTATION: return "PlayStation";
            default: return "经典";
        }
    }

    public static int next(int theme) {
        return theme == XBOX ? SWITCH : theme == SWITCH ? PLAYSTATION : XBOX;
    }

    /** Corner radius of the glass body, in pixels. */
    public static float radius(RectF r, int theme) {
        float small = Math.min(r.width(), r.height());
        switch (theme) {
            case SWITCH: return small * 0.5f;
            case PLAYSTATION: return small * 0.22f;
            default: return small * 0.36f;
        }
    }

    /** Accent colour of the theme, used for the active state and the thin edge. */
    public static int accent(int theme, boolean on) {
        switch (theme) {
            case SWITCH: return on ? Color.rgb(255, 84, 62) : Color.rgb(120, 214, 255);
            case PLAYSTATION: return on ? Color.rgb(120, 176, 255) : Color.rgb(210, 220, 235);
            default: return on ? Color.rgb(126, 214, 92) : Color.rgb(232, 240, 236);
        }
    }

    /**
     * Draws one glass key. The caller draws the label on top, with a normal Android font, so any
     * language shows up correctly.
     */
    public static void draw(Canvas canvas, RectF r, int theme, boolean on, boolean pressed) {
        float radius = radius(r, theme);
        int topAlpha = pressed ? 74 : on ? 58 : 34;
        int bottomAlpha = pressed ? 40 : on ? 26 : 14;

        glow.setShader(new RadialGradient(r.centerX(), r.top + r.height() * 0.28f, r.width() * 1.15f,
            new int[]{Color.argb(on ? 60 : 34, 255, 255, 255), Color.argb(0, 255, 255, 255)},
            new float[]{0f, 1f}, Shader.TileMode.CLAMP));
        canvas.drawRoundRect(r, radius, radius, glow);
        glow.setShader(null);

        body.setShader(new LinearGradient(0, r.top, 0, r.bottom,
            Color.argb(topAlpha, 246, 249, 252), Color.argb(bottomAlpha, 214, 222, 232), Shader.TileMode.CLAMP));
        canvas.drawRoundRect(r, radius, radius, body);
        body.setShader(null);

        line.setStyle(Paint.Style.STROKE);
        line.setStrokeWidth(Math.max(1f, r.height() * 0.035f));
        line.setColor(Color.argb(on ? 200 : 150, 255, 255, 255));
        tmp.set(r);
        tmp.inset(line.getStrokeWidth() * 0.5f, line.getStrokeWidth() * 0.5f);
        canvas.drawRoundRect(tmp, radius, radius, line);

        int accent = accent(theme, on);
        line.setColor(Color.argb(on ? 235 : 140, Color.red(accent), Color.green(accent), Color.blue(accent)));
        tmp.set(r.left + r.width() * 0.22f, r.bottom - line.getStrokeWidth() * 2.1f,
            r.right - r.width() * 0.22f, r.bottom - line.getStrokeWidth() * 0.6f);
        float ar = tmp.height() * 0.5f;
        canvas.drawRoundRect(tmp, ar, ar, line);
        line.setStyle(Paint.Style.FILL);
    }
}
