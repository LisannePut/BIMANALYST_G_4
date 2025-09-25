# BIManalyst group 04
# Façade Transparency Analysis

**Focus Area:** Architecture  
**Claim:** Façade transparency (57%) – *25-16-D-ARCH p. 3*  

---

## Background
Daylight is a frequently discussed theme in architecture and often a driving factor in the conceptual design of buildings.  
To evaluate the claimed façade transparency, we developed a script to analyze an **IFC building model** and verify the reported values.

---

## Methodology

The script determines façade transparency by:

1. **Identifying external walls**  
   - Filtering out certain wall names  
   - Checking property sets for the `IsExternal` property  

2. **Avoiding double-counting**  
   - Detecting overlapping bounding boxes of walls  

3. **Calculating areas**  
   - Summing the areas of unique external walls  
   - Summing the areas of all windows using property sets or direct attributes  

4. **Calculating transparency**  
   - Facade transparency =  
     \[
     \frac{\text{Total Window Area}}{\text{Total Façade Area}} \times 100
     \]

---

## Results

- **Number of windows:** *calculated by script*  
- **Total glazing area:** *calculated by script*  
- **Total exterior wall area:** *calculated by script*  
- **Window-to-wall ratio:** **45.91%**  

---

## Discussion of Discrepancy

The calculated transparency (**45.91%**) is lower than the claimed value (**57%**). Possible explanations include:

- **Overlapping façade elements**  
  Errors in the modeling process can increase the total surface area of exterior walls, lowering the ratio.  

- **Missing or misclassified elements**  
  Some windows or façade components may not be properly classified in the IFC file and thus not counted.  

- **Duplicate or misrepresented geometry**  
  Overlaps or misalignments in geometry can cause under- or over-counting of areas.  

---

## Conclusion

While the claim of **57% façade transparency** (25-16-D-ARCH, p. 3) is reported, our IFC-based analysis suggests a lower value of **45.91%**, likely influenced by modeling errors and classification issues.
