import LLMRouter from './router.js';

console.log('Starting CLI test...');

const router = new LLMRouter();
const input = process.argv.slice(2).join(' ') || 'こんにちは';

console.log(`Input: ${input}`);

router.route(input).then(result => {
  console.log('\n📄 応答:\n');
  console.log(result.response);
  console.log('\n');
  router.showStats();
}).catch(error => {
  console.error('❌ Error:', error.message);
  console.error(error.stack);
  process.exit(1);
});
