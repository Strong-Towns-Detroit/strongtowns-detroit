const origin = process.env.NEXT_PUBLIC_SITE_URL;
if (!origin) throw new Error('Set NEXT_PUBLIC_SITE_URL to the actual public HTTPS origin before building for deployment.');
const url=new URL(origin);
if(url.protocol!=='https:' || url.username || url.password || ['localhost','127.0.0.1'].includes(url.hostname) || /\.(example|invalid|test)$/.test(url.hostname)) throw new Error('Deployment requires the actual public HTTPS hostname.');
