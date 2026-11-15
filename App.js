import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  SafeAreaView,
  StatusBar,
  ActivityIndicator,
  Alert,
  Modal,
  Platform,
  RefreshControl,
} from 'react-native';

const DEFAULT_IP = '10.102.77.214';

export default function App() {
  const [ipAddress, setIpAddress] = useState(DEFAULT_IP);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Auth / Screen States: 'onboarding' | 'auth' | 'main'
  const [appState, setAppState] = useState('main'); 
  const [phone, setPhone] = useState('+998 90 123 45 67');
  const [password, setPassword] = useState('12345678');
  const [userName, setUserName] = useState('Dilshod');

  // Main Bottom Navigation: 'home' | 'transactions' | 'add' | 'reports' | 'profile'
  const [currentTab, setCurrentTab] = useState('home');

  // Home Screen States
  const [showBalance, setShowBalance] = useState(true);
  const [homeData, setHomeData] = useState({
    balance: 0,
    income: 0,
    expense: 0,
    monthly: [],
  });

  // Transactions State
  const [txFilter, setTxFilter] = useState('all'); // 'all' | 'income' | 'expense'
  const [transactions, setTransactions] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');

  // Add Screen State
  const [addType, setAddType] = useState('expense'); // 'expense' | 'income'
  const [addAmount, setAddAmount] = useState('');
  const [addCat, setAddCat] = useState('Oziq-ovqat');
  const [addDate, setAddDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [addDesc, setAddDesc] = useState('');

  // Report State
  const [reportPeriod, setReportPeriod] = useState('Oy'); // 'Oy' | 'Chorak' | 'Yil'
  const [reportData, setReportData] = useState({
    total_expense: 0,
    categories: [],
  });

  // Sub-modals / Screens
  const [categoryModal, setCategoryModal] = useState(false);
  const [bankModal, setBankModal] = useState(false);
  const [budgetModal, setBudgetModal] = useState(false);
  const [settingsModal, setSettingsModal] = useState(false);
  const [addBudgetModal, setAddBudgetModal] = useState(false);

  // Byudjetlar State
  const [budgets, setBudgets] = useState([]);
  const [budgetCatInput, setBudgetCatInput] = useState('Oziq-ovqat');
  const [budgetLimitInput, setBudgetLimitInput] = useState('');

  // Yangi kategoriya qo'shish
  const [newCatName, setNewCatName] = useState('');

  const [categoriesList, setCategoriesList] = useState([
    { name: 'Oziq-ovqat', icon: '🛒', color: '#fee2e2' },
    { name: 'Transport', icon: '🚗', color: '#dbeafe' },
    { name: 'Kommunal', icon: '💧', color: '#e0f2fe' },
    { name: 'Sog‘liq', icon: '❤️', color: '#fce7f3' },
    { name: 'Ta’lim', icon: '🎓', color: '#fef3c7' },
    { name: 'Ko‘ngilochar', icon: '🎮', color: '#dcfce7' },
    { name: 'Kiyim-kechak', icon: '👕', color: '#f3e8ff' },
    { name: 'Xaridlar', icon: '🛍️', color: '#fae8ff' },
    { name: 'Ish haqi', icon: '💼', color: '#dcfce7' },
    { name: 'Biznes', icon: '📈', color: '#fef9c3' },
    { name: 'Boshqa', icon: '💬', color: '#ede9fe' },
  ]);

  const getApiUrl = (endpoint) => `http://${ipAddress}:8000/api${endpoint}`;

  // ==========================================
  // REAL API DATA FETCHING
  // ==========================================
  const loadAllData = async () => {
    try {
      setRefreshing(true);

      // 1. Dashboard
      const dashRes = await fetch(getApiUrl('/dashboard?period=30%20kun'));
      if (dashRes.ok) {
        const dJson = await dashRes.json();
        
        // Hisoblangan oylik dinamika
        const monthlyBars = (dJson.monthly_summary || []).slice(-6).map((item) => {
          const maxExp = Math.max(...(dJson.monthly_summary || []).map((m) => m.expense || 1), 1);
          const pct = Math.max(15, Math.min(100, Math.round(((item.expense || 0) / maxExp) * 100)));
          return {
            month: item.month ? item.month.split('-')[1] || item.month : '',
            expensePct: pct,
          };
        });

        setHomeData({
          balance: dJson.all_metrics?.balance || 0,
          income: dJson.period_metrics?.total_income || 0,
          expense: dJson.period_metrics?.total_expense || 0,
          monthly: monthlyBars.length > 0 ? monthlyBars : [
            { month: 'Yan', expensePct: 40 },
            { month: 'Fev', expensePct: 65 },
            { month: 'Mar', expensePct: 50 },
            { month: 'Apr', expensePct: 80 },
            { month: 'May', expensePct: 60 },
            { month: 'Iyun', expensePct: 90 },
          ],
        });
      }

      // 2. Transactions
      const txRes = await fetch(getApiUrl('/transactions?limit=100'));
      if (txRes.ok) {
        const tJson = await txRes.json();
        setTransactions(tJson || []);
      }

      // 3. Budgets
      const bRes = await fetch(getApiUrl('/budgets'));
      if (bRes.ok) {
        const bJson = await bRes.json();
        setBudgets(bJson.budgets || []);
      }

      // 4. Reports
      const rRes = await fetch(getApiUrl(`/reports?period=${encodeURIComponent(reportPeriod)}`));
      if (rRes.ok) {
        const rJson = await rRes.json();
        const totalExp = rJson.metrics?.total_expense || 0;
        const cats = (rJson.category_expenses || []).map((c, i) => {
          const pct = totalExp > 0 ? Math.round((c.expense / totalExp) * 100) : 0;
          const colors = ['#ef4444', '#3b82f6', '#06b6d4', '#ec4899', '#f59e0b', '#8b5cf6', '#10b981'];
          return {
            name: c.category || 'Boshqa',
            val: c.expense,
            pct: `${pct}%`,
            col: colors[i % colors.length],
          };
        });
        setReportData({
          total_expense: totalExp,
          categories: cats,
        });
      }
    } catch (e) {
      console.log('Error loading data:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, [ipAddress, reportPeriod]);

  const fmt = (val) => (Number(val) || 0).toLocaleString('uz-UZ') + " so‘m";

  // ==========================================
  // TRANZAKSIYA SAQLASH (REAL POST)
  // ==========================================
  const handleSaveTransaction = async () => {
    const rawNum = parseFloat(String(addAmount).replace(/\s/g, ''));
    if (!rawNum || rawNum <= 0) {
      Alert.alert('Xatolik', 'Iltimos, summani kiriting!');
      return;
    }

    try {
      const res = await fetch(getApiUrl('/transactions'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount: rawNum,
          type: addType,
          category: addCat,
          description: addDesc,
          tx_date: addDate,
          source: 'Mobile App',
        }),
      });

      if (res.ok) {
        Alert.alert('✅ Muvaffaqiyatli', 'Operatsiya bazaga saqlandi!');
        setAddAmount('');
        setAddDesc('');
        loadAllData();
        setCurrentTab('transactions');
      } else {
        const err = await res.json();
        Alert.alert('Xatolik', err.detail || 'Operatsiyani saqlab bo‘lmadi');
      }
    } catch (e) {
      Alert.alert('Ulanish xatosi', 'Server bilan aloqa yo‘q. IP ni tekshiring.');
    }
  };

  // ==========================================
  // TRANZAKSIYANI O'CHIRISH (DELETE)
  // ==========================================
  const handleDeleteTx = (id, desc) => {
    Alert.alert(
      'O‘chirishni tasdiqlang',
      `"${desc || 'Ushbu operatsiya'}" o‘chirilsinmi?`,
      [
        { text: 'Bekor qilish', style: 'cancel' },
        {
          text: 'Ha, o‘chirish',
          style: 'destructive',
          onPress: async () => {
            try {
              const res = await fetch(getApiUrl(`/transactions/${id}`), { method: 'DELETE' });
              if (res.ok) {
                loadAllData();
              }
            } catch (e) {
              Alert.alert('Xatolik', 'O‘chirib bo‘lmadi');
            }
          },
        },
      ]
    );
  };

  // ==========================================
  // BYUDJET SAQLASH (REAL POST)
  // ==========================================
  const handleSaveBudget = async () => {
    const rawNum = parseFloat(String(budgetLimitInput).replace(/\s/g, ''));
    if (isNaN(rawNum) || rawNum <= 0) {
      Alert.alert('Xatolik', 'Limit summasini to‘g‘ri kiriting!');
      return;
    }

    try {
      const res = await fetch(getApiUrl('/budgets'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: budgetCatInput,
          limit_amount: rawNum,
        }),
      });

      if (res.ok) {
        Alert.alert('✅ Saqlandi', `${budgetCatInput} uchun byudjet belgilandi!`);
        setBudgetLimitInput('');
        setAddBudgetModal(false);
        loadAllData();
      }
    } catch (e) {
      Alert.alert('Xatolik', 'Serverga ulanib bo‘lmadi');
    }
  };

  // ==========================================
  // YANGI KATEGORIYA QO'SHISH
  // ==========================================
  const handleAddNewCategory = () => {
    if (!newCatName.trim()) return;
    const newCat = {
      name: newCatName.trim(),
      icon: '🏷️',
      color: '#e2e8f0',
    };
    setCategoriesList([...categoriesList, newCat]);
    setAddCat(newCat.name);
    setNewCatName('');
    setCategoryModal(false);
  };

  // Toifalar bo'yicha ikonka topish
  const getCategoryIcon = (catName) => {
    const found = categoriesList.find((c) => c.name.toLowerCase() === String(catName).toLowerCase());
    return found ? found.icon : '💬';
  };

  const getCategoryColor = (catName) => {
    const found = categoriesList.find((c) => c.name.toLowerCase() === String(catName).toLowerCase());
    return found ? found.color : '#f1f5f9';
  };

  // Tranzaksiyalar filtrlash
  const filteredTxs = transactions.filter((t) => {
    const isInc = (t.income || 0) > 0;
    if (txFilter === 'income' && !isInc) return false;
    if (txFilter === 'expense' && isInc) return false;
    if (searchQuery.trim() !== '') {
      const query = searchQuery.toLowerCase();
      const descMatch = String(t.description || '').toLowerCase().includes(query);
      const catMatch = String(t.category || '').toLowerCase().includes(query);
      return descMatch || catMatch;
    }
    return true;
  });

  return (
    <SafeAreaView style={styles.mainContainer}>
      <StatusBar barStyle="dark-content" backgroundColor="#f8fafc" />

      {/* ================= TAB 1: BOSH SAHIFA (HOME) ================= */}
      {currentTab === 'home' && (
        <ScrollView
          style={styles.screenScroll}
          contentContainerStyle={{ paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={loadAllData} />}
        >
          {/* Header */}
          <View style={styles.homeTopRow}>
            <View>
              <Text style={styles.homeGreeting}>Salom,</Text>
              <Text style={styles.homeName}>{userName}! 👋</Text>
            </View>
            <TouchableOpacity onPress={() => setSettingsModal(true)} style={styles.bellBtn}>
              <Text style={{ fontSize: 20 }}>⚙️</Text>
            </TouchableOpacity>
          </View>

          {/* Balance Card */}
          <View style={styles.homeBalanceCard}>
            <View style={styles.balanceHeaderRow}>
              <Text style={styles.balanceHeaderLabel}>Joriy balans</Text>
              <TouchableOpacity onPress={() => setShowBalance(!showBalance)}>
                <Text style={{ fontSize: 18 }}>{showBalance ? '👁️' : '🙈'}</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.balanceMainText}>
              {showBalance ? fmt(homeData.balance) : '•••••••• so‘m'}
            </Text>

            {/* Income & Expense Badges */}
            <View style={styles.statBadgesRow}>
              <View style={styles.badgeIncome}>
                <Text style={styles.badgeLabel}>↑ Kirim (Shu oy)</Text>
                <Text style={styles.badgeIncomeVal}>{fmt(homeData.income)}</Text>
              </View>

              <View style={styles.badgeExpense}>
                <Text style={styles.badgeLabel}>↓ Chiqim (Shu oy)</Text>
                <Text style={styles.badgeExpenseVal}>{fmt(homeData.expense)}</Text>
              </View>
            </View>
          </View>

          {/* Oylik Dinamika (Bar Chart) */}
          <View style={styles.chartCard}>
            <Text style={styles.chartTitle}>Oylik dinamika</Text>
            <View style={styles.barsContainer}>
              {homeData.monthly.map((m, idx) => (
                <View key={idx} style={styles.barItem}>
                  <View style={styles.barTrack}>
                    <View style={[styles.barFill, { height: `${m.expensePct}%` }]} />
                  </View>
                  <Text style={styles.barLabel}>{m.month}</Text>
                </View>
              ))}
            </View>
          </View>

          {/* Tezkor Funksiyalar (Bank aylanmasi / Byudjet) */}
          <View style={styles.quickTilesRow}>
            <TouchableOpacity style={styles.quickTile} onPress={() => setBankModal(true)}>
              <Text style={{ fontSize: 26, marginBottom: 6 }}>📊</Text>
              <Text style={styles.quickTileTitle}>Bank aylanmasi</Text>
              <Text style={styles.quickTileSub}>Excel import</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.quickTile} onPress={() => setBudgetModal(true)}>
              <Text style={{ fontSize: 26, marginBottom: 6 }}>🎯</Text>
              <Text style={styles.quickTileTitle}>Byudjetlar</Text>
              <Text style={styles.quickTileSub}>Limit nazorati</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      )}

      {/* ================= TAB 2: TRANZAKSIYALAR ================= */}
      {currentTab === 'transactions' && (
        <ScrollView
          style={styles.screenScroll}
          contentContainerStyle={{ paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={loadAllData} />}
        >
          <View style={styles.headerSection}>
            <Text style={styles.screenTitle}>Tranzaksiyalar</Text>
          </View>

          {/* Filter Pills */}
          <View style={styles.filterPillsRow}>
            {['Barchasi', 'Kirim', 'Chiqim'].map((f) => {
              const key = f === 'Barchasi' ? 'all' : f === 'Kirim' ? 'income' : 'expense';
              const active = txFilter === key;
              return (
                <TouchableOpacity
                  key={f}
                  style={[styles.pillBtn, active && styles.pillBtnActive]}
                  onPress={() => setTxFilter(key)}
                >
                  <Text style={[styles.pillBtnText, active && styles.pillBtnTextActive]}>
                    {f}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* Qidiruv Input */}
          <View style={{ paddingHorizontal: 20, marginBottom: 12 }}>
            <TextInput
              style={styles.searchBar}
              placeholder="🔍 Izoh yoki kategoriya bo‘yicha qidirish..."
              value={searchQuery}
              onChangeText={setSearchQuery}
            />
          </View>

          {/* Tranzaksiyalar Ro'yxati */}
          <View style={{ paddingHorizontal: 20 }}>
            {filteredTxs.length === 0 ? (
              <Text style={{ textAlign: 'center', color: '#94a3b8', marginVertical: 30 }}>
                Operatsiyalar topilmadi
              </Text>
            ) : (
              filteredTxs.map((item, idx) => {
                const isInc = (item.income || 0) > 0;
                const amt = isInc ? item.income : item.expense;
                return (
                  <TouchableOpacity
                    key={idx}
                    style={styles.txItemWhite}
                    onLongPress={() => handleDeleteTx(item.id, item.description)}
                  >
                    <View style={[styles.txIconCircle, { backgroundColor: getCategoryColor(item.category) }]}>
                      <Text style={{ fontSize: 18 }}>{getCategoryIcon(item.category)}</Text>
                    </View>
                    <View style={{ flex: 1, marginLeft: 12 }}>
                      <Text style={styles.txMainName}>{item.description || item.category || 'Operatsiya'}</Text>
                      <Text style={styles.txSubName}>{item.tx_date} · {item.category}</Text>
                    </View>
                    <View style={{ alignItems: 'flex-end' }}>
                      <Text style={[styles.txAmountText, { color: isInc ? '#10b981' : '#ef4444' }]}>
                        {isInc ? `+${fmt(amt)}` : `-${fmt(amt)}`}
                      </Text>
                      <Text style={styles.txTime}>{item.source || 'App'}</Text>
                    </View>
                  </TouchableOpacity>
                );
              })
            )}
          </View>
        </ScrollView>
      )}

      {/* ================= TAB 3: YANGI TRANZAKSIYA ================= */}
      {currentTab === 'add' && (
        <ScrollView style={styles.screenScroll} contentContainerStyle={{ paddingBottom: 100 }}>
          <View style={styles.subScreenHeader}>
            <TouchableOpacity onPress={() => setCurrentTab('home')}>
              <Text style={{ fontSize: 20 }}>←</Text>
            </TouchableOpacity>
            <Text style={styles.subScreenTitle}>Yangi tranzaksiya</Text>
            <View style={{ width: 20 }} />
          </View>

          {/* Chiqim / Kirim Switcher */}
          <View style={styles.switcherRow}>
            <TouchableOpacity
              style={[styles.switchHalfBtn, addType === 'expense' && styles.switchHalfExpense]}
              onPress={() => setAddType('expense')}
            >
              <Text style={[styles.switchHalfText, addType === 'expense' && { color: '#ef4444' }]}>
                Chiqim
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.switchHalfBtn, addType === 'income' && styles.switchHalfIncome]}
              onPress={() => setAddType('income')}
            >
              <Text style={[styles.switchHalfText, addType === 'income' && { color: '#10b981' }]}>
                Kirim
              </Text>
            </TouchableOpacity>
          </View>

          <View style={{ paddingHorizontal: 20 }}>
            {/* Summa Input */}
            <View style={styles.cardBox}>
              <Text style={styles.boxLabel}>Summa</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <TextInput
                  style={styles.summaInput}
                  value={addAmount}
                  onChangeText={setAddAmount}
                  placeholder="0"
                  keyboardType="numeric"
                />
                <Text style={{ color: '#94a3b8', fontSize: 16 }}>so‘m</Text>
              </View>
            </View>

            {/* Kategoriya Tanlash */}
            <TouchableOpacity
              style={styles.cardBoxRow}
              onPress={() => setCategoryModal(true)}
            >
              <View>
                <Text style={styles.boxLabel}>Kategoriya</Text>
                <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 4 }}>
                  <Text style={{ fontSize: 18, marginRight: 8 }}>{getCategoryIcon(addCat)}</Text>
                  <Text style={styles.cardBoxVal}>{addCat}</Text>
                </View>
              </View>
              <Text style={{ color: '#94a3b8', fontSize: 18 }}>›</Text>
            </TouchableOpacity>

            {/* Sana */}
            <View style={styles.cardBoxRow}>
              <View>
                <Text style={styles.boxLabel}>Sana (YYYY-MM-DD)</Text>
                <TextInput
                  style={[styles.cardBoxVal, { marginTop: 4 }]}
                  value={addDate}
                  onChangeText={setAddDate}
                />
              </View>
              <Text style={{ fontSize: 18 }}>📅</Text>
            </View>

            {/* Izoh */}
            <View style={styles.cardBox}>
              <Text style={styles.boxLabel}>Izoh (ixtiyoriy)</Text>
              <TextInput
                style={[styles.cardBoxVal, { marginTop: 4 }]}
                value={addDesc}
                onChangeText={setAddDesc}
                placeholder="Masalan: Tushlik, benzin..."
              />
            </View>

            {/* Saqlash Tugmasi */}
            <TouchableOpacity style={styles.btnGreenFull} onPress={handleSaveTransaction}>
              <Text style={styles.btnGreenFullText}>Saqlash</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      )}

      {/* ================= TAB 4: HISOBOT (REPORTS) ================= */}
      {currentTab === 'reports' && (
        <ScrollView
          style={styles.screenScroll}
          contentContainerStyle={{ paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={loadAllData} />}
        >
          <View style={styles.headerSection}>
            <Text style={styles.screenTitle}>Hisobot</Text>
          </View>

          {/* Oy / Chorak / Yil Filter */}
          <View style={styles.filterPillsRow}>
            {['Oy', 'Chorak', 'Yil'].map((p) => {
              const active = reportPeriod === p;
              return (
                <TouchableOpacity
                  key={p}
                  style={[styles.pillBtn, active && styles.pillBtnActive]}
                  onPress={() => setReportPeriod(p)}
                >
                  <Text style={[styles.pillBtnText, active && styles.pillBtnTextActive]}>
                    {p}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* Donut Chart Visual Card */}
          <View style={styles.donutCard}>
            <View style={styles.donutCircle}>
              <Text style={{ fontSize: 12, color: '#64748b' }}>Jami chiqim</Text>
              <Text style={{ fontSize: 20, fontWeight: '800', color: '#0f172a', marginVertical: 4 }}>
                {fmt(reportData.total_expense)}
              </Text>
              <Text style={{ fontSize: 11, color: '#64748b' }}>tanlangan davr</Text>
            </View>
          </View>

          {/* Categories List Breakdown */}
          <View style={{ paddingHorizontal: 20 }}>
            {reportData.categories.length === 0 ? (
              <Text style={{ textAlign: 'center', color: '#94a3b8', marginVertical: 20 }}>
                Xarajatlar mavjud emas
              </Text>
            ) : (
              reportData.categories.map((it, idx) => (
                <View key={idx} style={styles.reportRow}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <View style={[styles.colorDot, { backgroundColor: it.col }]} />
                    <Text style={{ fontSize: 14, fontWeight: '600', color: '#1e293b' }}>{it.name}</Text>
                  </View>
                  <Text style={{ fontSize: 13, color: '#64748b' }}>{it.pct}</Text>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: '#0f172a' }}>
                    {fmt(it.val)}
                  </Text>
                </View>
              ))
            )}
          </View>
        </ScrollView>
      )}

      {/* ================= TAB 5: PROFIL ================= */}
      {currentTab === 'profile' && (
        <ScrollView style={styles.screenScroll} contentContainerStyle={{ paddingBottom: 100 }}>
          <View style={styles.subScreenHeader}>
            <TouchableOpacity onPress={() => setCurrentTab('home')}>
              <Text style={{ fontSize: 20 }}>←</Text>
            </TouchableOpacity>
            <Text style={styles.subScreenTitle}>Profil</Text>
            <View style={{ width: 20 }} />
          </View>

          {/* User Card */}
          <View style={styles.profileUserCard}>
            <View style={styles.avatarCircle}>
              <Text style={{ fontSize: 28 }}>👤</Text>
            </View>
            <View style={{ marginLeft: 14 }}>
              <Text style={styles.profileUserName}>{userName} Karimov</Text>
              <Text style={styles.profileUserPhone}>{phone}</Text>
            </View>
          </View>

          {/* Settings List */}
          <View style={{ paddingHorizontal: 20 }}>
            {[
              { title: 'Server IP sozlamasi', icon: '🌐', action: () => setSettingsModal(true) },
              { title: 'Kategoriyalarni boshqarish', icon: '🏷️', action: () => setCategoryModal(true) },
              { title: 'Byudjetlar va limitlar', icon: '🎯', action: () => setBudgetModal(true) },
              { title: 'Bank hisobotini yuklash (Excel)', icon: '📄', action: () => setBankModal(true) },
              { title: 'Ma’lumotlarni qayta yuklash', icon: '🔄', action: loadAllData },
            ].map((item, idx) => (
              <TouchableOpacity key={idx} style={styles.profileItemRow} onPress={item.action}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                  <Text style={{ fontSize: 18 }}>{item.icon}</Text>
                  <Text style={{ fontSize: 15, fontWeight: '600', color: '#0f172a' }}>{item.title}</Text>
                </View>
                <Text style={{ color: '#94a3b8', fontSize: 18 }}>›</Text>
              </TouchableOpacity>
            ))}

            {/* Chiqish */}
            <TouchableOpacity
              style={[styles.profileItemRow, { marginTop: 14, borderBottomWidth: 0 }]}
              onPress={() => Alert.alert('Chiqish', 'Tizimdan chiqishni tasdiqlaysizmi?')}
            >
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <Text style={{ fontSize: 18 }}>🚪</Text>
                <Text style={{ fontSize: 15, fontWeight: '700', color: '#ef4444' }}>Chiqish</Text>
              </View>
            </TouchableOpacity>
          </View>
        </ScrollView>
      )}

      {/* ================= MODAL: KATEGORIYALAR ================= */}
      <Modal visible={categoryModal} animationType="slide">
        <SafeAreaView style={{ flex: 1, backgroundColor: '#f8fafc' }}>
          <View style={styles.subScreenHeader}>
            <TouchableOpacity onPress={() => setCategoryModal(false)}>
              <Text style={{ fontSize: 20 }}>←</Text>
            </TouchableOpacity>
            <Text style={styles.subScreenTitle}>Kategoriyalar</Text>
            <View style={{ width: 20 }} />
          </View>

          <ScrollView style={{ paddingHorizontal: 20 }}>
            {categoriesList.map((c, idx) => (
              <TouchableOpacity
                key={idx}
                style={styles.catSelectRow}
                onPress={() => {
                  setAddCat(c.name);
                  setCategoryModal(false);
                }}
              >
                <View style={[styles.catIconBox, { backgroundColor: c.color }]}>
                  <Text style={{ fontSize: 18 }}>{c.icon}</Text>
                </View>
                <Text style={{ fontSize: 15, fontWeight: '600', color: '#0f172a', flex: 1, marginLeft: 12 }}>
                  {c.name}
                </Text>
                <Text style={{ color: '#94a3b8', fontSize: 18 }}>›</Text>
              </TouchableOpacity>
            ))}

            {/* Yangi kategoriya kiritish maydoni */}
            <View style={{ marginTop: 20, padding: 14, backgroundColor: '#fff', borderRadius: 14 }}>
              <Text style={{ fontSize: 13, fontWeight: '700', color: '#64748b', marginBottom: 8 }}>
                Yangi kategoriya nomi:
              </Text>
              <TextInput
                style={styles.searchBar}
                placeholder="Masalan: Kofe, Ijara..."
                value={newCatName}
                onChangeText={setNewCatName}
              />
              <TouchableOpacity style={styles.btnGreenFull} onPress={handleAddNewCategory}>
                <Text style={styles.btnGreenFullText}>＋ Qo‘shish</Text>
              </TouchableOpacity>
            </View>
          </ScrollView>
        </SafeAreaView>
      </Modal>

      {/* ================= MODAL: BYUDJETLAR ================= */}
      <Modal visible={budgetModal} animationType="slide">
        <SafeAreaView style={{ flex: 1, backgroundColor: '#f8fafc' }}>
          <View style={styles.subScreenHeader}>
            <TouchableOpacity onPress={() => setBudgetModal(false)}>
              <Text style={{ fontSize: 20 }}>←</Text>
            </TouchableOpacity>
            <Text style={styles.subScreenTitle}>Byudjetlar</Text>
            <TouchableOpacity onPress={() => setAddBudgetModal(true)}>
              <Text style={{ fontSize: 24, color: '#047857' }}>＋</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={{ paddingHorizontal: 20 }}>
            {budgets.length === 0 ? (
              <Text style={{ textAlign: 'center', color: '#94a3b8', marginVertical: 30 }}>
                Hozircha byudjetlar belgilanmagan
              </Text>
            ) : (
              budgets.map((b, idx) => {
                const pct = b.limit > 0 ? Math.min(100, Math.round((b.spent / b.limit) * 100)) : 0;
                const isOver = b.spent > b.limit;
                return (
                  <View key={idx} style={styles.budgetItemCard}>
                    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text style={{ fontSize: 15, fontWeight: '700', color: '#0f172a' }}>{b.category}</Text>
                      <Text style={{ fontSize: 13, fontWeight: '800', color: isOver ? '#ef4444' : '#059669' }}>
                        {pct}%
                      </Text>
                    </View>
                    <Text style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                      {fmt(b.spent)} / {fmt(b.limit)}
                    </Text>

                    <View style={styles.budgetTrack}>
                      <View style={[styles.budgetFill, { width: `${pct}%`, backgroundColor: isOver ? '#ef4444' : '#059669' }]} />
                    </View>
                  </View>
                );
              })
            )}

            <TouchableOpacity style={[styles.btnSecondary, { marginTop: 16 }]} onPress={() => setAddBudgetModal(true)}>
              <Text style={styles.btnSecondaryText}>＋ Yangi limit qo‘shish</Text>
            </TouchableOpacity>
          </ScrollView>

          {/* Add Budget Sub-modal */}
          <Modal visible={addBudgetModal} transparent={true} animationType="fade">
            <View style={styles.modalBg}>
              <View style={styles.modalBox}>
                <Text style={{ fontSize: 18, fontWeight: '800', color: '#0f172a', marginBottom: 12 }}>
                  Byudjet limiti
                </Text>

                <Text style={styles.boxLabel}>Kategoriya</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
                  {categoriesList.map((c) => (
                    <TouchableOpacity
                      key={c.name}
                      style={[styles.pillBtn, budgetCatInput === c.name && styles.pillBtnActive]}
                      onPress={() => setBudgetCatInput(c.name)}
                    >
                      <Text style={[styles.pillBtnText, budgetCatInput === c.name && styles.pillBtnTextActive]}>
                        {c.name}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>

                <Text style={styles.boxLabel}>Oylik limit (so‘m)</Text>
                <TextInput
                  style={styles.searchBar}
                  placeholder="Masalan: 3000000"
                  keyboardType="numeric"
                  value={budgetLimitInput}
                  onChangeText={setBudgetLimitInput}
                />

                <View style={{ flexDirection: 'row', gap: 10, marginTop: 14 }}>
                  <TouchableOpacity style={[styles.pillBtn, { flex: 1, alignItems: 'center' }]} onPress={() => setAddBudgetModal(false)}>
                    <Text style={styles.pillBtnText}>Bekor qilish</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.btnGreenFull, { flex: 1, marginTop: 0 }]} onPress={handleSaveBudget}>
                    <Text style={styles.btnGreenFullText}>Saqlash</Text>
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          </Modal>
        </SafeAreaView>
      </Modal>

      {/* ================= MODAL: BANK AYLANMASI (EXCEL) ================= */}
      <Modal visible={bankModal} animationType="slide">
        <SafeAreaView style={{ flex: 1, backgroundColor: '#f8fafc' }}>
          <View style={styles.subScreenHeader}>
            <TouchableOpacity onPress={() => setBankModal(false)}>
              <Text style={{ fontSize: 20 }}>←</Text>
            </TouchableOpacity>
            <Text style={styles.subScreenTitle}>Bank aylanmasi</Text>
            <View style={{ width: 20 }} />
          </View>

          <View style={{ padding: 24, alignItems: 'center', marginTop: 40 }}>
            <View style={styles.excelIconBig}>
              <Text style={{ fontSize: 48 }}>📊</Text>
            </View>
            <Text style={{ fontSize: 20, fontWeight: '800', color: '#0f172a', marginTop: 16 }}>
              Bank hisoboti (Excel)
            </Text>
            <Text style={{ textAlign: 'center', color: '#64748b', fontSize: 13, marginTop: 8, lineHeight: 20 }}>
              Bankingizdan olingan .xlsx yoki .csv faylni import qilib, barcha tranzaksiyalarni bittada avtomatik qo‘shing.
            </Text>

            <TouchableOpacity
              style={[styles.btnGreenFull, { width: '100%', marginTop: 32 }]}
              onPress={() => {
                Alert.alert(
                  'Excel yuklash',
                  'Faylni kompyuterdan Web Dashboard orqali yuklash eng qulay yo‘l hisoblanadi (http://localhost:8501).'
                );
              }}
            >
              <Text style={styles.btnGreenFullText}>📂 Fayl tanlash (.xlsx, .csv)</Text>
            </TouchableOpacity>

            <View style={styles.infoBadgeBox}>
              <Text style={{ fontSize: 14 }}>ℹ️</Text>
              <View style={{ marginLeft: 8 }}>
                <Text style={{ fontSize: 12, fontWeight: '700', color: '#047857' }}>Qo‘llab-quvvatlanadi:</Text>
                <Text style={{ fontSize: 11, color: '#065f46' }}>• Barcha O‘zbekiston banklari fayllari{'\n'}• Takrorlanishdan avtomatik himoya</Text>
              </View>
            </View>
          </View>
        </SafeAreaView>
      </Modal>

      {/* ================= MODAL: SETTINGS (IP SOZLAMASI) ================= */}
      <Modal visible={settingsModal} transparent={true} animationType="fade">
        <View style={styles.modalBg}>
          <View style={styles.modalBox}>
            <Text style={{ fontSize: 18, fontWeight: '800', color: '#0f172a', marginBottom: 8 }}>
              Server IP Sozlamasi
            </Text>
            <Text style={{ fontSize: 13, color: '#64748b', marginBottom: 12 }}>
              Kompyuteringiz lokal Wi-Fi IP manzili:
            </Text>
            <TextInput
              style={styles.searchBar}
              value={ipAddress}
              onChangeText={setIpAddress}
              placeholder="10.102.77.214"
            />
            <View style={{ flexDirection: 'row', gap: 10, marginTop: 12 }}>
              <TouchableOpacity style={[styles.pillBtn, { flex: 1, alignItems: 'center' }]} onPress={() => setSettingsModal(false)}>
                <Text style={styles.pillBtnText}>Yopish</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.btnGreenFull, { flex: 1, marginTop: 0 }]}
                onPress={() => {
                  setSettingsModal(false);
                  loadAllData();
                }}
              >
                <Text style={styles.btnGreenFullText}>Ulanish</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ================= PASTKI NAVIGATSIYA (BOTTOM NAV) ================= */}
      <View style={styles.bottomNavContainer}>
        {/* Bosh sahifa */}
        <TouchableOpacity style={styles.navTabItem} onPress={() => setCurrentTab('home')}>
          <Text style={{ fontSize: 20 }}>🏠</Text>
          <Text style={[styles.navTabLabel, currentTab === 'home' && styles.navTabLabelActive]}>
            Bosh sahifa
          </Text>
        </TouchableOpacity>

        {/* Tranzaksiyalar */}
        <TouchableOpacity style={styles.navTabItem} onPress={() => setCurrentTab('transactions')}>
          <Text style={{ fontSize: 20 }}>🧾</Text>
          <Text style={[styles.navTabLabel, currentTab === 'transactions' && styles.navTabLabelActive]}>
            Tranzaksiyalar
          </Text>
        </TouchableOpacity>

        {/* Markazdagi Dumaloq Katta + Tugma */}
        <TouchableOpacity style={styles.navCenterFab} onPress={() => setCurrentTab('add')}>
          <Text style={styles.navCenterFabText}>＋</Text>
        </TouchableOpacity>

        {/* Hisobot */}
        <TouchableOpacity style={styles.navTabItem} onPress={() => setCurrentTab('reports')}>
          <Text style={{ fontSize: 20 }}>📊</Text>
          <Text style={[styles.navTabLabel, currentTab === 'reports' && styles.navTabLabelActive]}>
            Hisobot
          </Text>
        </TouchableOpacity>

        {/* Profil */}
        <TouchableOpacity style={styles.navTabItem} onPress={() => setCurrentTab('profile')}>
          <Text style={{ fontSize: 20 }}>👤</Text>
          <Text style={[styles.navTabLabel, currentTab === 'profile' && styles.navTabLabelActive]}>
            Profil
          </Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  mainContainer: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  screenScroll: {
    flex: 1,
  },
  homeTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 12,
  },
  homeGreeting: {
    fontSize: 14,
    color: '#64748b',
  },
  homeName: {
    fontSize: 22,
    fontWeight: '900',
    color: '#0f172a',
  },
  bellBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    justifyContent: 'center',
    alignItems: 'center',
  },
  homeBalanceCard: {
    marginHorizontal: 20,
    backgroundColor: '#064e3b',
    borderRadius: 24,
    padding: 22,
    marginTop: 8,
    shadowColor: '#064e3b',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.2,
    shadowRadius: 16,
    elevation: 8,
  },
  balanceHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  balanceHeaderLabel: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.7)',
    fontWeight: '600',
  },
  balanceMainText: {
    fontSize: 30,
    fontWeight: '900',
    color: '#ffffff',
    marginVertical: 10,
  },
  statBadgesRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 10,
  },
  badgeIncome: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.95)',
    borderRadius: 16,
    padding: 12,
  },
  badgeExpense: {
    flex: 1,
    backgroundColor: 'rgba(255,255,255,0.95)',
    borderRadius: 16,
    padding: 12,
  },
  badgeLabel: {
    fontSize: 11,
    color: '#64748b',
    fontWeight: '600',
  },
  badgeIncomeVal: {
    fontSize: 14,
    fontWeight: '800',
    color: '#059669',
    marginTop: 4,
  },
  badgeExpenseVal: {
    fontSize: 14,
    fontWeight: '800',
    color: '#dc2626',
    marginTop: 4,
  },
  chartCard: {
    marginHorizontal: 20,
    backgroundColor: '#ffffff',
    borderRadius: 20,
    padding: 18,
    marginTop: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  chartTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#0f172a',
    marginBottom: 16,
  },
  barsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    height: 120,
    paddingTop: 10,
  },
  barItem: {
    alignItems: 'center',
    flex: 1,
  },
  barTrack: {
    width: 14,
    height: 90,
    backgroundColor: '#f1f5f9',
    borderRadius: 8,
    justifyContent: 'flex-end',
    overflow: 'hidden',
  },
  barFill: {
    backgroundColor: '#10b981',
    borderRadius: 8,
    width: '100%',
  },
  barLabel: {
    fontSize: 11,
    color: '#64748b',
    marginTop: 6,
    fontWeight: '600',
  },
  quickTilesRow: {
    flexDirection: 'row',
    gap: 12,
    marginHorizontal: 20,
    marginTop: 16,
  },
  quickTile: {
    flex: 1,
    backgroundColor: '#ffffff',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  quickTileTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0f172a',
  },
  quickTileSub: {
    fontSize: 11,
    color: '#64748b',
    marginTop: 2,
  },
  headerSection: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 8,
  },
  screenTitle: {
    fontSize: 24,
    fontWeight: '900',
    color: '#0f172a',
  },
  filterPillsRow: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    gap: 8,
    marginVertical: 12,
  },
  pillBtn: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
    backgroundColor: '#f1f5f9',
  },
  pillBtnActive: {
    backgroundColor: '#047857',
  },
  pillBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#64748b',
  },
  pillBtnTextActive: {
    color: '#ffffff',
  },
  searchBar: {
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#e2e8f0',
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    color: '#0f172a',
  },
  txItemWhite: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    padding: 14,
    borderRadius: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#f1f5f9',
  },
  txIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  txMainName: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0f172a',
  },
  txSubName: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 2,
  },
  txAmountText: {
    fontSize: 15,
    fontWeight: '800',
  },
  txTime: {
    fontSize: 11,
    color: '#94a3b8',
    marginTop: 2,
  },
  subScreenHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  subScreenTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0f172a',
  },
  switcherRow: {
    flexDirection: 'row',
    marginHorizontal: 20,
    backgroundColor: '#f1f5f9',
    borderRadius: 16,
    padding: 4,
    marginBottom: 16,
  },
  switchHalfBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 12,
    alignItems: 'center',
  },
  switchHalfExpense: {
    backgroundColor: '#fee2e2',
  },
  switchHalfIncome: {
    backgroundColor: '#d1fae5',
  },
  switchHalfText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#64748b',
  },
  cardBox: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 12,
  },
  cardBoxRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 14,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 12,
  },
  boxLabel: {
    fontSize: 11,
    color: '#64748b',
    fontWeight: '600',
    marginBottom: 4,
  },
  cardBoxVal: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0f172a',
  },
  summaInput: {
    fontSize: 24,
    fontWeight: '800',
    color: '#0f172a',
    flex: 1,
    marginTop: 2,
  },
  btnGreenFull: {
    backgroundColor: '#047857',
    paddingVertical: 16,
    borderRadius: 16,
    alignItems: 'center',
    marginTop: 8,
  },
  btnGreenFullText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '800',
  },
  donutCard: {
    alignItems: 'center',
    marginVertical: 18,
  },
  donutCircle: {
    width: 170,
    height: 170,
    borderRadius: 85,
    borderWidth: 16,
    borderColor: '#10b981',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#ffffff',
  },
  reportRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f5f9',
  },
  colorDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  profileUserCard: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 20,
    backgroundColor: '#ffffff',
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 16,
  },
  avatarCircle: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: '#d1fae5',
    justifyContent: 'center',
    alignItems: 'center',
  },
  profileUserName: {
    fontSize: 17,
    fontWeight: '800',
    color: '#0f172a',
  },
  profileUserPhone: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 2,
  },
  profileItemRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    padding: 16,
    borderRadius: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#f1f5f9',
  },
  catSelectRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    padding: 14,
    borderRadius: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#f1f5f9',
  },
  catIconBox: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  excelIconBig: {
    width: 90,
    height: 90,
    borderRadius: 24,
    backgroundColor: '#dcfce7',
    justifyContent: 'center',
    alignItems: 'center',
  },
  infoBadgeBox: {
    flexDirection: 'row',
    backgroundColor: '#ecfdf5',
    borderRadius: 14,
    padding: 14,
    width: '100%',
    marginTop: 24,
    borderWidth: 1,
    borderColor: '#a7f3d0',
  },
  budgetItemCard: {
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginBottom: 12,
  },
  budgetTrack: {
    height: 8,
    backgroundColor: '#f1f5f9',
    borderRadius: 4,
    marginTop: 10,
    overflow: 'hidden',
  },
  budgetFill: {
    height: '100%',
    backgroundColor: '#059669',
    borderRadius: 4,
  },
  btnSecondary: {
    backgroundColor: '#ecfdf5',
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#a7f3d0',
  },
  btnSecondaryText: {
    color: '#047857',
    fontSize: 15,
    fontWeight: '700',
  },
  modalBg: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalBox: {
    backgroundColor: '#ffffff',
    borderRadius: 20,
    padding: 20,
    width: '100%',
  },
  bottomNavContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 70,
    backgroundColor: '#ffffff',
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
    paddingBottom: Platform.OS === 'ios' ? 14 : 0,
  },
  navTabItem: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  navTabLabel: {
    fontSize: 10,
    color: '#94a3b8',
    fontWeight: '600',
    marginTop: 3,
  },
  navTabLabelActive: {
    color: '#047857',
    fontWeight: '800',
  },
  navCenterFab: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#047857',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: -22,
    shadowColor: '#047857',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  navCenterFabText: {
    color: '#ffffff',
    fontSize: 28,
    lineHeight: 30,
    fontWeight: '300',
  },
});
