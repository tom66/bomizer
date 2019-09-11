import csv, time, copy, sys

distributors = [
    { 'name' : 'Digi-Key', 
      'min_order' : 33.00, 
      'shipping_before_min' : 12.00, 
      'shipping_after_min': 0.00,
      'mult_import_tax' : 1.0,
      'csv_columns' : ['SKU', 'OrderQty', 'RefDesList'],
      'csv_column_names' : ['SKU', 'Quantity', 'Description'] },
    { 'name' : 'Arrow Electronics, Inc.',
      'min_order' : 40.70, 
      'shipping_before_min' : 10.57, 
      'shipping_after_min': 0.00,
      'mult_import_tax' : 1.0,
      'csv_columns' : ['SKU', 'OrderQty', 'RefDesList'],
      'csv_column_names' : ['SKU', 'Quantity', 'Description'] },
    { 'name' : 'Avnet',    
      'min_order' : 0.0, 
      'shipping_before_min' : 30.93, 
      'shipping_after_min': 30.93,
      'mult_import_tax' : 1.2,
      'csv_columns' : ['SKU', 'OrderQty', 'RefDesList'],
      'csv_column_names' : ['SKU', 'Quantity', 'Description'] }, # Import tax multiplier as not DDP
    { 'name' : 'Farnell',    
      'min_order' : 0.0, 
      'shipping_before_min' : 3.95, 
      'shipping_after_min': 0.0,
      'mult_import_tax' : 1.0,
      'csv_columns' : ['SKU', 'OrderQty', 'RefDesList'],
      'csv_column_names' : ['SKU', 'Quantity', 'Description'] },
    { 'name' : 'Mouser',    
      'min_order' : 33.00, 
      'shipping_before_min' : 12.00, 
      'shipping_after_min': 0.0,
      'mult_import_tax' : 1.0,
      'csv_columns' : ['SKU', 'OrderQty', 'RefDesList'],
      'csv_column_names' : ['SKU', 'Quantity', 'Description'] },
    { 'name' : 'RS Components',    
      'min_order' : 0.00, 
      'shipping_before_min' : 0.0, 
      'shipping_after_min': 0.0,
      'mult_import_tax' : 1.0,
      'csv_columns' : ['SKU', 'OrderQty', 'RefDesList', 'MPNRef'],
      'csv_column_names' : ['SKU', 'Quantity', 'Description', 'MPN'] },
    { 'name' : 'TME',    
      'min_order' : 0.00, 
      'shipping_before_min' : 5.70, 
      'shipping_after_min': 5.70,
      'mult_import_tax' : 1.0,
      'csv_columns' : ['SKU', 'OrderQty', 'RefDesList'],
      'csv_column_names' : ['SKU', 'Quantity', 'Description'] }
]

footprint_extra_required = ['0402', '0603', '0805', '1206', '1812', '2512']
refdes_must_include = ['R', 'C', 'FB']
footprint_minimum_excess = 20
footprint_minimum_required = 30

# max characters in any refdes description
refdes_str_max_len = 15

# Scenario A: cheapest line from each taken
distributor_orders_scenario_A = []
distributor_summary_scenario_A = {}

# Scenario B: attempt to aggregate small orders where shipping costs more than 30% of the total order 
distributor_orders_scenario_B = []
distributor_summary_scenario_B = {}

# Scenario C: attempt to eliminate all distributors that charge shipping
distributor_orders_scenario_C = []
distributor_summary_scenario_C = {}

input_file = '20190908_scopy_mvp__s_fixed_.csv'
ifp = open(input_file, 'r')
cs = csv.reader(ifp)

# Change this to compute scenarios at different quantities but beware that it will not update
# for differing price breaks
qty_multiplier = 2

# Process first two rows to decode header positions
print("")
print("** Processing header and extracting distributor columns **")

header_positions = {}

header_top = next(cs)
header_disty = next(cs)

keys = ['SKU', 'Unit Price', 'In Stock', 'MOQ']
ignore = '(Selected)'

for n, col in enumerate(header_top):
    for key in keys:
        if key not in header_positions:
            header_positions[key] = []
            
        if col.startswith(key) and col.find(ignore) == -1:
            #print(key, header_disty[n])
            header_positions[key].append((n, header_disty[n]))

def multireplace(st_, find, subst):
    for f in find:
        st_ = st_.replace(f, subst)
    return st_
            
def get_distributor(dist):
    for disty in distributors:
        if disty['name'] == dist:
            return disty
            
    raise KeyError("unable to find %r" % dist)
            
def get_column(dist, key):
    col = header_positions[key]
    
    for data in col:
        if data[1] == dist:
            return data
    
    return None

def save_scenario(name, order):
    dist_orders = {}

    for line in order:
        d = line['ChosenOption']['Dist']
        if d not in dist_orders:
            dist_orders[d] = []
        dist_orders[d].append(line['ChosenOption'])
    
    print("")
    
    for dist in dist_orders:
        dist_data = get_distributor(dist)
        
        fname = "%s_%s_order.csv" % (name, multireplace(dist, '. ,-', '_'))
        fp = open(fname, "w")
        dist_cs = csv.writer(fp)
        dist_cs.writerow(dist_data['csv_column_names'])
        
        for row in dist_orders[dist]:
            row_out = []
            for col in dist_data['csv_columns']:
                row_out.append(row[col])
            dist_cs.writerow(row_out)
        
        fp.close()
    
def summarise_scenario(name, items):
    print("")
    print("** Summary for Scenario %s **" % name)
    print("")
    
    total_cost = 0.0
    dist_totals = {}
    dist_totals_incl_shipping = {}
    dist_qtys = {}
    dist_lines = {}
    
    for line in items:
        chosen = line['ChosenOption']
        
        if chosen['Dist'] not in dist_totals:
            dist_totals[chosen['Dist']] = 0.0
            dist_qtys[chosen['Dist']] = 0
            dist_lines[chosen['Dist']] = 0
        
        dist_totals[chosen['Dist']] += chosen['LinePrice']
        dist_qtys[chosen['Dist']] += chosen['OrderQty']
        dist_lines[chosen['Dist']] += 1
    
    # Compute shipping costs
    dist_totals_incl_shipping = copy.copy(dist_totals)
    dist_summary = []
    total_cost = 0.0
    total_lines = 0
    
    for dist, value in dist_totals.items():
        dist_data = get_distributor(dist)
        shipping = 0.0
        
        if value < dist_data['min_order']:
            shipping = dist_data['shipping_before_min']
        else:
            shipping = dist_data['shipping_after_min']
        
        value += shipping
        value *= dist_data['mult_import_tax']
        total_cost += value
        total_lines += dist_lines[dist]
        
        print("Order %d parts in %d lines from %s, total %2.2f (shipping %2.2f)" % (dist_qtys[dist], dist_lines[dist], dist, value, shipping))
        dist_summary.append([dist, value, shipping, dist_qtys[dist], dist_lines[dist]])
    
    print("Total cost %2.2f" % total_cost)
    print("Total orders %d" % len(dist_summary))
    print("Total lines %d" % total_lines)
    
    return dist_summary
    
def find_cheapest(lines, exclude):
    order = []
    
    for line in lines:
        lowest_line_cost = 9e99
        excluded_line_lowest_cost = 9e99
        lowest_line = None
        excluded_line = None    
        
        for dist in line['SourceOptions']:
            option = line['SourceOptions'][dist]
            
            if dist in exclude:
                if option['LinePrice'] <= excluded_line_lowest_cost:
                    excluded_line = {'Line' : line, 'ChosenOption' : option}
                    excluded_line_lowest_cost = option['LinePrice']
                continue
            
            if option['LinePrice'] <= lowest_line_cost:
                lowest_line = {'Line' : line, 'ChosenOption' : option}
                lowest_line_cost = option['LinePrice']
            
            #print(dist, line['SourceOptions'][dist])
            #print(option)

        #print(line['SourceOptions'])
        #print("")
        #print(lowest_line)
        #print("")
                
        if lowest_line == None:
            if len(exclude) > 0:
                print("Unable to exclude %r from distributors as required for order..." % exclude)
                lowest_line = excluded_line
            else:
                raise RuntimeError("Unable to solve %r!" % line)
            
        order.append(lowest_line)
    
    return order
        
# Catalogue all items according to distributor, unit price, MOQ
line_items = []

# Process all rows.  Duplicate MPNs are merged.
duplicate_line = {}
rows_without_duplicates = []

for row in cs:
    # Extract SKU and store in duplicate line dict.  If this already exists compute an increased
    # quantity and combine refdeses
    if row[3] not in duplicate_line:
        duplicate_line[row[3]] = [row]
    else:
        duplicate_line[row[3]].append(row)

for mpn, row in duplicate_line.items():
    if len(row) == 1:
        rows_without_duplicates.append(row[0])
    else:
        new_row = row[0]

        for sub_row in row[1:]:
            print("%s has duplicate; merging in quantity %d (+%d existing) refdes list %s" % (sub_row[3], int(sub_row[0]), int(new_row[0]), sub_row[5]))
            new_row[0] = int(new_row[0]) + int(sub_row[0])
            new_row[5] += ", %s" % sub_row[5]
            
        rows_without_duplicates.append(new_row)

for row in rows_without_duplicates:
    # Compute minimum quantity required for assembly
    qty = int(row[0]) * qty_multiplier
    min_reqd_qty = qty
    refdeses = row[5].split(",")
    is_small_smd = False
    
    for rd in refdeses:
        trim = rd.strip()
        for inc in refdes_must_include:
            if trim.startswith(inc):
                is_small_smd = True
    
    #print(refdeses, is_small_smd)
    
    for fp in footprint_extra_required:
        if row[7].find(fp) != -1:
            if is_small_smd:
                qty += footprint_minimum_excess
                break

    if is_small_smd:
        if qty < footprint_minimum_required:
            qty = footprint_minimum_required
    
    refdes_string = " ".join(map(str.strip, refdeses))
    if len(refdes_string) > refdes_str_max_len:
        # trim to nearest whole refdes (look for space)
        tpos = refdes_string[0:refdes_str_max_len - 1].rfind(' ')
        refdes_string = refdes_string[0:tpos] + ".."
    
    refdes_string = refdes_string.strip()
    
    #print(row)
    #print(qty)
    #print("")
    
    # print(refdes_string)
    
    row_data = {
        'TotalOrderableQty' : qty,
        'MPN' : row[3],
        'SchRef' : row[5],
        'SourceOptions' : {}
    }
    
    # For each distributor append the MOQ required
    for dist in distributors:
        dist_name = dist['name']
        dist_rowdata = {}
        
        # Find MOQ column
        moq_col = get_column(dist_name, "MOQ")
        try:
            moq_dist = int(row[moq_col[0]])
        except:
            #print("*** Note: %s cannot supply %s - not stocked" % (dist_name, row_data['MPN']))
            continue    
        
        # Find SKU
        sku_col = get_column(dist_name, "SKU")
        sku_dist = row[sku_col[0]]
        
        # Filter for out of stock items (Qty > Stock or not stocked at all)
        stock_col = get_column(dist_name, "In Stock")
        try:
            stock_dist = int(row[stock_col[0]])
        except:
            stock_dist = 0
        
        if stock_dist < row_data['TotalOrderableQty']:
            #print("*** Note: %s cannot supply %s (In Stock %d - Need %d)" % (dist_name, row_data['MPN'], stock_dist, row_data['TotalOrderableQty']))
            continue
        
        # Find unit price
        try:
            unit_price_col = get_column(dist_name, "Unit Price")
            unit_price_dist = float(row[unit_price_col[0]])
        except:
            #print("*** Note: %s cannot supply %s - Invalid Price" % (dist_name, row_data['MPN']))
            continue
        
        # Add the row even if MOQ is high; this is included as a potential scenario (ordering more components than required)
        order_qty = row_data['TotalOrderableQty']
        #print(order_qty)
        if moq_dist > order_qty:
            order_qty = moq_dist
        
        line_price_dist = order_qty * unit_price_dist
        
        #print("Note: %s supplies %s at %d (build min. %d) ... line price %2.2f" % (dist_name, row_data['MPN'], order_qty, min_reqd_qty, line_price_dist))
        #time.sleep(0.1)
        
        dist_rowdata = { 'Dist' : dist_name,
                         'OrderQty' : order_qty,
                         'SKU' : sku_dist,
                         'UnitPrice' : unit_price_dist,
                         'LinePrice' : line_price_dist,
                         'RefDesList' : refdes_string,
                         'MPNRef' : row_data['MPN'] }
        
        row_data['SourceOptions'][dist_name] = dist_rowdata

    #print(row_data['SourceOptions'])
        
    line_items.append(row_data)

# Initial scenario is to choose the cheapest line price of each item and build orders for each distributor
print("")
print("** Running initial scenario A: cheapest items from any distributor **")

distributor_orders_scenario_A = find_cheapest(line_items, [])
distributor_summary_scenario_A = summarise_scenario('A (Lowest Cost)', distributor_orders_scenario_A)
save_scenario('A', distributor_orders_scenario_A)
#print(distributor_summary_scenario_A)
#print(distributor_orders_scenario_A)

print("")
print("** Running modified scenario B: aggregating small orders with shipping charges **")

exclude = []

for dist in distributor_summary_scenario_A:
    if dist[2] > (dist[1] * 0.3):
        print("Elimating %s as shipping costs large proportion of order" % dist[0])
        exclude.append(dist[0])

distributor_orders_scenario_B = find_cheapest(line_items, exclude)
distributor_summary_scenario_B = summarise_scenario('B (Reduce Shipping Costs)', distributor_orders_scenario_B)
save_scenario('B', distributor_orders_scenario_B)
#print(distributor_summary_scenario_B)
#print(distributor_orders_scenario_B)

print("")
print("** Running modified scenario C: eliminate all shipping charges if possible **")

exclude = []

for dist in distributor_summary_scenario_A:
    if dist[2] > 0:
        print("Elimating %s as shipping costs present" % dist[0])
        exclude.append(dist[0])

distributor_orders_scenario_C = find_cheapest(line_items, exclude)
distributor_summary_scenario_C = summarise_scenario('C (Eliminate Shipping Costs)', distributor_orders_scenario_C)
save_scenario('C', distributor_orders_scenario_C)
#print(distributor_summary_scenario_C)
#print(distributor_orders_scenario_C)

ifp.close()

