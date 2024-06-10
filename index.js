const express = require('express');
const path = require('path');
const bodyParser = require('body-parser');
const mongoose = require('mongoose');
const ejs = require('ejs');
const Order = require('./models/ordermodel');

const app = express();

// Middleware
app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());

// EJS Ayarları
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

// Statik Dosyalar
app.use(express.static(path.join(__dirname, 'public')));

// MongoDB Bağlantısı
mongoose.connect('mongodb://localhost:27017/ecommerce-single', {
  useNewUrlParser: true,
  useUnifiedTopology: true,
}).then(() => {
  console.log('MongoDB bağlantısı başarılı');
}).catch(err => {
  console.log('MongoDB bağlantısı hatası:', err);
});

// Rotalar
app.get('/', (req, res) => {
  res.render('anasayfa');
});

app.get('/mangal', (req, res) => {
  res.render('mangal');
});

app.post('/order', async (req, res) => {
  const { name, address, quantity } = req.body;
  try {
    const newOrder = new Order({ name, address, quantity });
    await newOrder.save();
    res.send('Siparişiniz alınmıştır. Teşekkür ederiz!');
  } catch (error) {
    res.status(500).send('Sipariş kaydedilirken bir hata oluştu.');
  }
});

// Sunucu Başlatma
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Sunucu ${PORT} portunda çalışıyor`);
});
