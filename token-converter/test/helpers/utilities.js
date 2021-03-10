const checkGetOrders = (orders, _ordersIds, _ordersAmounts) => {
  let i = 0;
  let checkOrdersOk = true;
  let ordersIdsBN = orders[0].slice();
  let ordersAmountsBN = orders[1].slice();

  let ordersIds = ordersIdsBN.filter((item) => item.toNumber() !== 0);
  let ordersAmounts = ordersAmountsBN.filter((item) => item.toNumber() !== 0);

  while (i < ordersIds.length) {
    if (ordersIds[i].toNumber() != _ordersIds[i]) {
      checkOrdersOk = false;
      break;
    }
    if (ordersAmounts[i].toNumber() != _ordersAmounts[i]) {
      checkOrdersOk = false;
      break;
    }
    i++;
  }
  return { checkOrdersOk, qty: i };
};

const checkTokenOrders = (orders, _ordersIds, _ordersToken) => {
  let i = 0;
  let checkOrdersOk = true;
  let ordersIdsBN = orders[0].slice();
  let ordersTokenBN = orders[2].slice();

  let ordersIds = ordersIdsBN.filter((item) => item.toNumber() !== 0);
  let ordersToken = ordersTokenBN.filter((item) => item.toString() !== 0);

  while (i < ordersIds.length) {
    if (ordersIds[i].toNumber() != _ordersIds[i]) {
      checkOrdersOk = false;
      break;
    }
    if (ordersToken[i].toString() != _ordersToken[i]) {
      checkOrdersOk = false;
      break;
    }
    i++;
  }
  return checkOrdersOk;
};

const makeSellOrder = async (
  converterContract,
  amount,
  tokenAddress,
  sellerAddress,
  txOption
) => {
  const tx = await converterContract.onTokensMinted(
    amount,
    tokenAddress,
    web3.eth.abi.encodeParameter("address", sellerAddress),
    txOption
  );

  const makeSellOrderLog = tx.logs[1];
  return makeSellOrderLog.args._orderId.toNumber();
};

module.exports = {
  checkGetOrders,
  makeSellOrder,
  checkTokenOrders,
};
