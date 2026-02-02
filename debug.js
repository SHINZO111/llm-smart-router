console.log('=== Debug Start ===');
console.log('Node version:', process.version);
console.log('Arguments:', process.argv);
console.log('CWD:', process.cwd());
console.log('API Key set:', !!process.env.ANTHROPIC_API_KEY);
console.log('=== Debug End ===');

import('./router.js').then(() => {
  console.log('Router loaded successfully');
}).catch(err => {
  console.error('Error loading router:', err.message);
  console.error(err.stack);
});
