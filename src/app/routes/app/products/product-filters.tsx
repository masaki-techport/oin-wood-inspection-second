import Button from '@/components/ui/button';
import { GetProductFilter } from '@/features/products/api';
import { Grid, IconButton, TextField } from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers';
import moment from 'moment';
import { Dispatch, SetStateAction, useState } from 'react';
import FilterAltOffIcon from '@mui/icons-material/FilterAltOff';

type ProductFiltersProp = {
  filter: GetProductFilter;
  setFilter: Dispatch<SetStateAction<GetProductFilter>>;
};
const ProductFilters = ({ filter, setFilter }: ProductFiltersProp) => {
  const [filterProductNo, setFilterProductNo] = useState(filter.productNo);
  const [filterProductName, setFilterProductName] = useState(
    filter.productName,
  );
  const [from, setFrom] = useState<moment.Moment | null>(
    (filter.fromDate && moment(filter.fromDate)) || null,
  );
  const [to, setTo] = useState<moment.Moment | null>(
    (filter.toDate && moment(filter.toDate)) || null,
  );
  const handleFilter = () => {
    setFilter((prevState) => ({
      ...prevState,
      productNo: filterProductNo,
      productName: filterProductName,
      fromDate: from && from.isValid() ? from.toDate() : undefined,
      toDate: to && to.isValid() ? to.toDate() : undefined,
    }));
  };
  const isFiltered =
    (filterProductNo !== undefined && filterProductNo !== '') ||
    (filterProductName !== undefined && filterProductName !== '') ||
    from !== null ||
    to !== null;
  return (
    <div className="flex flex-row item-center">
      <Grid container spacing={2} alignItems="center">
        <Grid item xs={2}>
          <TextField
            label="品番"
            value={filterProductNo}
            onChange={(event) => setFilterProductNo(event.target.value)}
            margin="normal"
            fullWidth
          />
        </Grid>
        <Grid item xs={2}>
          <TextField
            label="品名"
            value={filterProductName}
            onChange={(event) => setFilterProductName(event.target.value)}
            margin="normal"
            fullWidth
          />
        </Grid>
        <Grid item xs={2}>
          <DateTimePicker
            label="from"
            sx={{ width: '100%' }}
            value={from}
            onChange={(value) => setFrom(value)}
          />
        </Grid>
        <Grid item xs={2}>
          <DateTimePicker
            label="to"
            sx={{ width: '100%' }}
            value={to}
            onChange={(value) => setTo(value)}
          />
        </Grid>
        <Grid item xs={2}>
          <Button onClick={handleFilter}>検索</Button>
        </Grid>
        <Grid item xs={1}>
          <IconButton
            color="primary"
            disabled={!isFiltered}
            onClick={() => {
              setFilterProductNo('');
              setFilterProductName('');
              setFrom(null);
              setTo(null);
            }}
          >
            <FilterAltOffIcon />
          </IconButton>
        </Grid>
      </Grid>
    </div>
  );
};

export default ProductFilters;
