package com.winlator.d2;

import android.annotation.SuppressLint;
import android.content.Context;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.FrameLayout;








@SuppressLint("ViewConstructor")
final class D2LaunchButton extends FrameLayout {
    private final Runnable action;

    private final int kind;
    private String text;
    private D2SettingsLook look;

    D2LaunchButton(Context context, String text, Runnable action) {
        this(context, D2ButtonTiers.MAIN, text, action);
    }

    D2LaunchButton(Context context, int kind, String text, Runnable action) {
        super(context);
        this.kind = kind;
        this.text = text;
        this.action = action;
        look = D2SettingsLook.get();
        int gap = Math.round(3 * context.getResources().getDisplayMetrics().density);
        setPadding(0, gap, 0, gap);
        build();
    }

    void setText(int id) {
        setText(getContext().getString(id));
    }

    void setText(String text) {
        if (text.equals(this.text)) return;
        this.text = text;
        build();
    }


    void useLook(D2SettingsLook look) {
        if (look == null || look == this.look) return;
        this.look = look;
        build();
    }

    @Override
    public void setEnabled(boolean enabled) {
        super.setEnabled(enabled);
        if (getChildCount() > 0) getChildAt(0).setEnabled(enabled);
    }

    private void build() {
        // Launcher controls always use the same native glass treatment.
        removeAllViews();
        Button button = new Button(getContext());
        button.setText(text);
        D2Style.button(button, getResources().getDisplayMetrics().density);
        button.setOnClickListener((v) -> action.run());
        button.setEnabled(isEnabled());
        addView(button, new LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
    }
}
