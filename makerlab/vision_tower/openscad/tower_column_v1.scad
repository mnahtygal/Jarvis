/*
  JARVIS Maker Lab
  Vision Tower V1 - Tower Column

  Print orientation: upright, as modeled
  Material target: ASA
  Printer target: Bambu A1
  Supports: none

  Default output is the full 200 mm column.
  Change render_mode to "fit_test" for a short 30 mm coupon.
*/

$fn = 48;

// ---------- User parameters ----------
render_mode = "column";   // "column" or "fit_test"

column_outer = 60;        // outside width/depth, mm
wall_thickness = 3;       // primary wall thickness, mm
column_height = 200;      // full column height, mm
fit_test_height = 30;     // short validation coupon, mm

corner_radius = 3;        // outside corner radius, mm
inside_corner_radius = 1; // inside corner radius, mm

rib_depth = 2.0;          // internal stiffening rib projection, mm
rib_width = 3.0;          // internal stiffening rib width, mm

lead_in_height = 2.0;     // insertion chamfer height, mm
lead_in_reduction = 0.6;  // total width reduction at bottom, mm

// ---------- Derived values ----------
inner_size = column_outer - 2 * wall_thickness;
active_height = render_mode == "fit_test" ? fit_test_height : column_height;

assert(column_outer > 2 * wall_thickness,
       "column_outer must be larger than twice wall_thickness");
assert(corner_radius > wall_thickness,
       "corner_radius must be greater than wall_thickness");
assert(active_height > lead_in_height,
       "active height must exceed lead-in height");

// ---------- Helpers ----------
module rounded_square(size, radius) {
    offset(r = radius)
        square([size - 2 * radius, size - 2 * radius], center = true);
}

module rounded_square_tube_2d() {
    difference() {
        rounded_square(column_outer, corner_radius);
        rounded_square(inner_size, inside_corner_radius);
    }
}

module vertical_ribs(height) {
    // Four shallow ribs centered on the inside faces.
    // They increase stiffness while keeping the center open for cabling.
    inner_half = inner_size / 2;

    translate([0,  inner_half - rib_depth / 2, height / 2])
        cube([rib_width, rib_depth, height], center = true);

    translate([0, -inner_half + rib_depth / 2, height / 2])
        cube([rib_width, rib_depth, height], center = true);

    translate([ inner_half - rib_depth / 2, 0, height / 2])
        cube([rib_depth, rib_width, height], center = true);

    translate([-inner_half + rib_depth / 2, 0, height / 2])
        cube([rib_depth, rib_width, height], center = true);
}

module lead_in_section() {
    // Slightly reduced lower edge to help the column enter the base receiver.
    linear_extrude(
        height = lead_in_height,
        scale = column_outer / (column_outer - lead_in_reduction)
    )
        offset(delta = -lead_in_reduction / 2)
            rounded_square_tube_2d();
}

module main_column(height) {
    union() {
        lead_in_section();

        translate([0, 0, lead_in_height])
            linear_extrude(height = height - lead_in_height)
                rounded_square_tube_2d();

        vertical_ribs(height);
    }
}

// ---------- Output ----------
main_column(active_height);
