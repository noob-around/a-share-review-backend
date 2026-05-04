package com.stockreview.app;

import android.Manifest;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.GridLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int REQ_WRITE_STORAGE = 1001;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    private TextView statusText;
    private TextView directionText;
    private TextView hotText;
    private TextView warningText;
    private TextView limitUpText;
    private TextView limitDownText;
    private TextView risingText;
    private TextView fallingText;
    private ProgressBar progressBar;
    private Button fetchButton;
    private Button downloadButton;

    private int latestReviewId = -1;
    private String latestTradeDate = "";
    private long latestDownloadId = -1L;

    private final BroadcastReceiver downloadReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            long id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L);
            if (id == latestDownloadId) {
                openDownloadedExcel(id);
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildLayout());
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(downloadReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE), RECEIVER_EXPORTED);
        } else {
            registerReceiver(downloadReceiver, new IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE));
        }
        downloadButton.setEnabled(false);
        validateConfig();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        unregisterReceiver(downloadReceiver);
        executor.shutdownNow();
    }

    private View buildLayout() {
        FrameLayout root = new FrameLayout(this);

        ImageView background = new ImageView(this);
        background.setImageResource(getResources().getIdentifier("stock_bg", "drawable", getPackageName()));
        background.setScaleType(ImageView.ScaleType.CENTER_CROP);
        root.addView(background, new FrameLayout.LayoutParams(-1, -1));

        View dim = new View(this);
        dim.setBackgroundColor(Color.argb(150, 7, 10, 13));
        root.addView(dim, new FrameLayout.LayoutParams(-1, -1));

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(20), dp(42), dp(20), dp(28));
        scroll.addView(content, new ScrollView.LayoutParams(-1, -2));
        root.addView(scroll, new FrameLayout.LayoutParams(-1, -1));

        TextView eyebrow = text("A股 · 今日市场", 14, 0xFFE8C36A, Typeface.BOLD);
        content.addView(eyebrow);

        TextView title = text("智能复盘看板", 32, Color.WHITE, Typeface.BOLD);
        title.setPadding(0, dp(6), 0, dp(6));
        content.addView(title);

        TextView subtitle = text("获取实时市场概览，生成 AI 复盘，并下载 Excel 表格。", 15, 0xFFDDE4EA, Typeface.NORMAL);
        subtitle.setLineSpacing(dp(2), 1.0f);
        content.addView(subtitle);

        content.addView(spacer(18));

        LinearLayout summaryCard = card();
        directionText = text("等待获取股市信息", 22, Color.WHITE, Typeface.BOLD);
        summaryCard.addView(directionText);
        hotText = text("热点板块将在复盘完成后显示", 14, 0xFFBFC8D2, Typeface.NORMAL);
        hotText.setPadding(0, dp(10), 0, 0);
        summaryCard.addView(hotText);
        content.addView(summaryCard);

        content.addView(spacer(14));

        GridLayout grid = new GridLayout(this);
        grid.setColumnCount(2);
        content.addView(grid);

        limitUpText = metric(grid, "涨停家数", "--", 0xFFD23A31);
        limitDownText = metric(grid, "跌停家数", "--", 0xFF31B77E);
        risingText = metric(grid, "上涨家数", "--", 0xFFD23A31);
        fallingText = metric(grid, "下跌家数", "--", 0xFF31B77E);

        content.addView(spacer(14));

        LinearLayout actionCard = card();
        statusText = text("已连接线上后端，点击按钮开始。", 14, 0xFFE6EDF2, Typeface.NORMAL);
        actionCard.addView(statusText);

        progressBar = new ProgressBar(this);
        progressBar.setIndeterminate(true);
        progressBar.setVisibility(View.GONE);
        LinearLayout.LayoutParams progressParams = new LinearLayout.LayoutParams(-2, -2);
        progressParams.gravity = Gravity.CENTER_HORIZONTAL;
        progressParams.topMargin = dp(12);
        actionCard.addView(progressBar, progressParams);

        fetchButton = button("获取目前股市信息", 0xFFD23A31);
        fetchButton.setOnClickListener(v -> startReview());
        actionCard.addView(fetchButton);

        downloadButton = button("下载并打开 Excel 表格", 0xFFE8C36A);
        downloadButton.setTextColor(0xFF151515);
        downloadButton.setOnClickListener(v -> downloadExcel());
        actionCard.addView(downloadButton);

        warningText = text("", 13, 0xFFFFD6A0, Typeface.NORMAL);
        warningText.setPadding(0, dp(12), 0, 0);
        actionCard.addView(warningText);

        content.addView(actionCard);
        return root;
    }

    private void validateConfig() {
        if (TextUtils.isEmpty(BuildConfig.APP_TOKEN)) {
            setStatus("缺少 APP_TOKEN：请在 android/local.properties 中配置 APP_TOKEN。", false);
            fetchButton.setEnabled(false);
        }
    }

    private void startReview() {
        setLoading(true, "正在提交复盘任务...");
        warningText.setText("");
        downloadButton.setEnabled(false);
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("refresh", true);
                body.put("include_operations", false);
                body.put("async_mode", true);
                JSONObject created = requestJson("POST", "/api/reviews/daily", body);
                int reviewId = created.getInt("id");
                latestReviewId = reviewId;
                latestTradeDate = created.optString("trade_date", "");
                runOnUiThread(() -> setStatus("复盘任务已创建，正在抓取市场数据...", true));
                pollReview(reviewId);
            } catch (Exception e) {
                runOnUiThread(() -> setLoading(false, "获取失败：" + e.getMessage()));
            }
        });
    }

    private void pollReview(int reviewId) throws Exception {
        JSONObject latest = null;
        for (int i = 0; i < 36; i++) {
            Thread.sleep(i == 0 ? 3000 : 10000);
            latest = requestJson("GET", "/api/reviews/" + reviewId, null);
            String status = latest.optString("status");
            JSONObject finalLatest = latest;
            runOnUiThread(() -> setStatus("生成状态：" + translateStatus(finalLatest.optString("status")), true));
            if ("completed".equals(status) || "failed".equals(status)) {
                break;
            }
        }
        if (latest == null) {
            throw new IllegalStateException("没有拿到复盘状态");
        }
        JSONObject result = latest;
        runOnUiThread(() -> renderReview(result));
    }

    private void renderReview(JSONObject review) {
        String status = review.optString("status");
        if (!"completed".equals(status)) {
            setLoading(false, "复盘未完成：" + translateStatus(status));
            warningText.setText(review.optJSONObject("summary") == null ? "" : collectWarnings(review.optJSONObject("summary")));
            return;
        }

        JSONObject summary = review.optJSONObject("summary");
        if (summary == null) {
            setLoading(false, "复盘结果为空");
            return;
        }

        directionText.setText(summary.optString("market_direction", "复盘完成"));
        limitUpText.setText(String.valueOf(summary.optInt("limit_up_count", 0)));
        limitDownText.setText(String.valueOf(summary.optInt("limit_down_count", 0)));
        risingText.setText(String.valueOf(summary.optInt("rising_count", 0)));
        fallingText.setText(String.valueOf(summary.optInt("falling_count", 0)));
        hotText.setText(formatHotspots(summary.optJSONArray("daily_hotspots")));
        warningText.setText(collectWarnings(summary));
        downloadButton.setEnabled(true);
        setLoading(false, "复盘完成，可下载 Excel 表格。");
    }

    private void downloadExcel() {
        if (latestReviewId <= 0) {
            toast("请先获取股市信息");
            return;
        }
        if (Build.VERSION.SDK_INT <= 28 && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, REQ_WRITE_STORAGE);
            return;
        }

        DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        String datePart = TextUtils.isEmpty(latestTradeDate) ? new SimpleDateFormat("yyyyMMdd", Locale.CHINA).format(new Date()) : latestTradeDate.replace("-", "");
        String filename = "A股复盘_" + datePart + ".xlsx";
        Uri uri = Uri.parse(BuildConfig.API_BASE_URL + "/api/reviews/" + latestReviewId + "/excel");
        DownloadManager.Request request = new DownloadManager.Request(uri)
                .setTitle("A股复盘表格")
                .setDescription("正在下载 " + filename)
                .addRequestHeader("X-App-Token", BuildConfig.APP_TOKEN)
                .setMimeType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, filename);
        latestDownloadId = manager.enqueue(request);
        toast("开始下载，完成后会自动打开");
    }

    private void openDownloadedExcel(long id) {
        DownloadManager manager = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        Uri uri = manager.getUriForDownloadedFile(id);
        if (uri == null) {
            toast("下载完成，但未找到文件");
            return;
        }
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(uri, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        try {
            startActivity(intent);
        } catch (Exception e) {
            toast("已下载到 Downloads，请安装表格应用后打开");
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_WRITE_STORAGE && grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            downloadExcel();
        } else if (requestCode == REQ_WRITE_STORAGE) {
            toast("需要存储权限才能保存到下载目录");
        }
    }

    private JSONObject requestJson(String method, String path, JSONObject body) throws Exception {
        URL url = new URL(BuildConfig.API_BASE_URL + path);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod(method);
        conn.setConnectTimeout(30000);
        conn.setReadTimeout(120000);
        conn.setRequestProperty("Accept", "application/json");
        conn.setRequestProperty("X-App-Token", BuildConfig.APP_TOKEN);
        if (body != null) {
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (OutputStream os = conn.getOutputStream()) {
                os.write(body.toString().getBytes(StandardCharsets.UTF_8));
            }
        }
        int code = conn.getResponseCode();
        InputStream input = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
        String text = readAll(input);
        conn.disconnect();
        if (code >= 400) {
            throw new IllegalStateException("HTTP " + code + ": " + text);
        }
        return new JSONObject(text);
    }

    private String readAll(InputStream input) throws Exception {
        if (input == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
        }
        return sb.toString();
    }

    private String formatHotspots(JSONArray hotspots) {
        if (hotspots == null || hotspots.length() == 0) {
            return "暂无热点板块数据";
        }
        StringBuilder sb = new StringBuilder("热点板块：");
        int count = Math.min(3, hotspots.length());
        for (int i = 0; i < count; i++) {
            JSONObject item = hotspots.optJSONObject(i);
            if (item == null) {
                continue;
            }
            if (i > 0) {
                sb.append(" · ");
            }
            sb.append(item.optString("sector", "未知")).append("(").append(item.optInt("limit_up_count", 0)).append(")");
        }
        return sb.toString();
    }

    private String collectWarnings(JSONObject summary) {
        JSONObject quality = summary.optJSONObject("data_quality");
        JSONArray warnings = quality == null ? null : quality.optJSONArray("warnings");
        if (warnings == null || warnings.length() == 0) {
            return "";
        }
        StringBuilder sb = new StringBuilder("提示：");
        for (int i = 0; i < warnings.length(); i++) {
            if (i > 0) {
                sb.append("；");
            }
            sb.append(warnings.optString(i));
        }
        return sb.toString();
    }

    private String translateStatus(String status) {
        if ("generating".equals(status)) return "正在生成";
        if ("completed".equals(status)) return "已完成";
        if ("failed".equals(status)) return "失败";
        return status;
    }

    private void setLoading(boolean loading, String message) {
        progressBar.setVisibility(loading ? View.VISIBLE : View.GONE);
        fetchButton.setEnabled(!loading);
        setStatus(message, loading);
    }

    private void setStatus(String message, boolean active) {
        statusText.setText(message);
        statusText.setTextColor(active ? 0xFFE8C36A : 0xFFE6EDF2);
    }

    private TextView metric(GridLayout grid, String label, String value, int accent) {
        LinearLayout box = card();
        GridLayout.LayoutParams params = new GridLayout.LayoutParams();
        params.width = 0;
        params.height = ViewGroup.LayoutParams.WRAP_CONTENT;
        params.columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f);
        params.setMargins(dp(4), dp(4), dp(4), dp(4));
        box.setLayoutParams(params);

        TextView labelView = text(label, 13, 0xFFC8D0D8, Typeface.NORMAL);
        TextView valueView = text(value, 26, accent, Typeface.BOLD);
        valueView.setPadding(0, dp(6), 0, 0);
        box.addView(labelView);
        box.addView(valueView);
        grid.addView(box);
        return valueView;
    }

    private LinearLayout card() {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(18), dp(16), dp(18), dp(16));
        card.setBackground(new RoundedDrawable(0xD91A2027, dp(8), 0x33FFFFFF));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, dp(4), 0, dp(4));
        card.setLayoutParams(params);
        return card;
    }

    private Button button(String label, int color) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(15);
        button.setTextColor(Color.WHITE);
        button.setAllCaps(false);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setBackground(new RoundedDrawable(color, dp(8), 0x00000000));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, dp(52));
        params.setMargins(0, dp(14), 0, 0);
        button.setLayoutParams(params);
        return button;
    }

    private TextView text(String value, int sp, int color, int style) {
        TextView text = new TextView(this);
        text.setText(value);
        text.setTextSize(sp);
        text.setTextColor(color);
        text.setTypeface(Typeface.DEFAULT, style);
        return text;
    }

    private View spacer(int heightDp) {
        View view = new View(this);
        view.setLayoutParams(new LinearLayout.LayoutParams(1, dp(heightDp)));
        return view;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }
}
