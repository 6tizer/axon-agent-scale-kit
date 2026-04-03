/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",   // static export for nginx
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
