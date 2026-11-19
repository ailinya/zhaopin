import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react(), tailwindcss()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    server: {
        host: true, // 同时监听 0.0.0.0 + [::]（IPv4 + IPv6），局域网设备也能访问
        port: 5173,
        strictPort: true, // 端口被占用直接报错（避免静默切到 5174）
        proxy: {
            // 开发时把 /api 代理到 FastAPI 后端
            "/api": {
                target: "http://localhost:8000",
                changeOrigin: true,
            },
            // SSE 端点需要特殊配置（参考 §13.6）
            "/api/interviews/.+/events": {
                target: "http://localhost:8000",
                changeOrigin: true,
                ws: false, // SSE 不需要 ws
                // proxy_http_version 已在 nginx 中设置
            },
        },
    },
    build: {
        outDir: "dist",
        sourcemap: true,
        // chunk 大小警告阈值 500KB（§2.3 Week 3 验收标准）
        chunkSizeWarningLimit: 500,
    },
});
