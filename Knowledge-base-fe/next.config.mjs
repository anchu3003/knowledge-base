/** @type {import('next').NextConfig} */
const nextConfig = {
    typescript: {
        // KB-4.6 (Q1): build FAIL nếu type sai — bật lại để `npm run build` tin được.
        ignoreBuildErrors: false,
    },
    images: {
        unoptimized: true,
    },
}

export default nextConfig
