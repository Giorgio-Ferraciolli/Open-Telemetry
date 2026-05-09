const express = require('express');
const { propagation, context, trace, metrics } = require('@opentelemetry/api');

const app = express();

// Métrica de negócio
const meter = metrics.getMeter('api-node.business');
const stockLookups = meter.createCounter('app.stock.lookups.total', {
  description: 'Total de consultas de estoque',
});

// Estoque "fake"
const STOCK = { 1: 42, 2: 0, 3: 7 };

app.get('/', (req, res) => {
  res.json({ service: 'api-node', ok: true });
});

app.get('/stock/:pid', (req, res) => {
  const pid = parseInt(req.params.pid, 10);
  const stock = STOCK[pid];

  // lê a baggage que veio do api-python
  const bag = propagation.getBaggage(context.active());
  const customerId = bag?.getEntry('customer.id')?.value || 'unknown';

  // pega o span ativo (criado pela auto-instrumentação) e adiciona atributos
  const span = trace.getActiveSpan();
  span?.setAttribute('customer.id', customerId);
  span?.setAttribute('product.id', pid);

  const delay = 50 + Math.random() * 150;
  setTimeout(() => {
    if (stock === undefined) {
      span?.addEvent('produto desconhecido', { pid });
      stockLookups.add(1, { 'product.id': String(pid), found: 'false' });
      return res.status(404).json({ error: 'produto desconhecido' });
    }
    span?.setAttribute('stock.units', stock);
    stockLookups.add(1, { 'product.id': String(pid), found: 'true', 'in_stock': stock > 0 ? 'yes' : 'no' });
    res.json({ product_id: pid, in_stock: stock });
  }, delay);
});

const PORT = 8000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`api-node ouvindo em :${PORT}`);
});
